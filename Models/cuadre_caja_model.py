"""
§7.3 — Cuadre de caja.

La fórmula del total la calculaba el navegador y **no contaba el efectivo ni
el saldo anterior**:

    tarjetas + consignacion + factura_cxc + factura_credito - gastos_turno

Un cuadre de caja que no cuenta el efectivo no cuadra nada. La fórmula
correcta suma todo lo que entró y resta lo que salió:

    total_movimiento = saldo_anterior + efectivo + tarjetas + consignacion
                       + factura_cxc + factura_credito - gastos_turno

`total_movimiento` ya no se acepta del cliente: lo calcula el servidor a
partir de los componentes.
"""
from decimal import Decimal

import mysql.connector

from database import get_connection
from utils.fechas import a_fecha, rango_del_dia

# Componentes que suman al cuadre, y el único que resta.
SUMAN = ('saldo_anterior', 'efectivo', 'tarjetas', 'consignacion',
         'factura_cxc', 'factura_credito')
RESTAN = ('gastos_turno',)

CAMPOS = SUMAN + RESTAN


def calcular_total(data):
    """La fórmula del cuadre, en un solo sitio y en el servidor."""
    total = Decimal('0.00')
    for campo in SUMAN:
        total += Decimal(str(data.get(campo, 0) or 0))
    for campo in RESTAN:
        total -= Decimal(str(data.get(campo, 0) or 0))
    return total


class CuadreCajaModel:

    def _select(self, where='', params=(), orden='c.fecha DESC'):
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(
                f"""
                SELECT c.*,
                       CONCAT(e.nombre, ' ', e.apellido) AS empleado_nombre
                FROM cuadre_caja c
                LEFT JOIN empleados e ON c.empleado_id = e.id
                {where}
                ORDER BY {orden}
                """,
                params,
            )
            return cursor.fetchall()
        finally:
            cursor.close()
            conn.close()

    def get_all(self):
        return self._select()

    def get_by_id(self, id):
        filas = self._select('WHERE c.id = %s', (id,))
        return filas[0] if filas else None

    def get_by_fecha(self, fecha):
        return self._select('WHERE c.fecha = %s', (a_fecha(fecha),),
                            orden='c.creado_en DESC')

    def resumen_del_dia(self, fecha):
        """
        Lo que realmente entró ese día según los pagos registrados, para
        contrastarlo con lo que declara el cuadre.

        El día es el día calendario de Bogotá: se filtra por rango
        [inicio, fin) y no por `DATE(fecha_pago)`, así un pago de las 20:30
        cae en el cuadre de hoy y no en el de mañana (F16).
        """
        inicio, fin = rango_del_dia(fecha)
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(
                """
                SELECT p.metodo,
                       COALESCE(SUM(p.monto), 0) AS total,
                       COUNT(*) AS cantidad
                FROM pagos p
                WHERE p.anulado = 0
                  AND p.fecha_pago >= %s AND p.fecha_pago < %s
                GROUP BY p.metodo
                """,
                (inicio, fin),
            )
            por_metodo = cursor.fetchall()

            cursor.execute(
                """
                SELECT COALESCE(SUM(monto), 0) AS total
                FROM gastos WHERE fecha = %s
                """,
                (a_fecha(fecha),),
            )
            gastos = cursor.fetchone()['total']

            return {
                'fecha': a_fecha(fecha),
                'pagos_por_metodo': por_metodo,
                'total_pagos': sum(Decimal(str(m['total'])) for m in por_metodo),
                'total_gastos': gastos,
            }
        finally:
            cursor.close()
            conn.close()

    def create(self, data, empleado_id=None):
        total = calcular_total(data)
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO cuadre_caja (
                    empleado_id, fecha, saldo_anterior, efectivo,
                    gastos_turno, tarjetas, consignacion, factura_cxc,
                    factura_credito, total_movimiento, observaciones
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    empleado_id,
                    a_fecha(data['fecha']),
                    data.get('saldo_anterior', 0),
                    data.get('efectivo', 0),
                    data.get('gastos_turno', 0),
                    data.get('tarjetas', 0),
                    data.get('consignacion', 0),
                    data.get('factura_cxc', 0),
                    data.get('factura_credito', 0),
                    total,
                    data.get('observaciones'),
                ),
            )
            conn.commit()
            return cursor.lastrowid
        except mysql.connector.Error:
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()

    def update(self, id, data, empleado_id=None):
        """
        Recalcula el total sobre los valores resultantes, mezclando lo que
        llega con lo que ya estaba: así un PUT parcial no descuadra el total.
        """
        actual = self.get_by_id(id)
        if not actual:
            return 0

        mezcla = {campo: data.get(campo, actual.get(campo)) for campo in CAMPOS}
        total = calcular_total(mezcla)

        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                UPDATE cuadre_caja SET
                    fecha            = %s,
                    saldo_anterior   = %s,
                    efectivo         = %s,
                    gastos_turno     = %s,
                    tarjetas         = %s,
                    consignacion     = %s,
                    factura_cxc      = %s,
                    factura_credito  = %s,
                    total_movimiento = %s,
                    observaciones    = %s
                WHERE id = %s
                """,
                (
                    a_fecha(data.get('fecha')) or actual['fecha'],
                    mezcla['saldo_anterior'],
                    mezcla['efectivo'],
                    mezcla['gastos_turno'],
                    mezcla['tarjetas'],
                    mezcla['consignacion'],
                    mezcla['factura_cxc'],
                    mezcla['factura_credito'],
                    total,
                    data.get('observaciones', actual.get('observaciones')),
                    id,
                ),
            )
            conn.commit()
            return cursor.rowcount or 1
        except mysql.connector.Error:
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()

    def delete(self, id):
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('DELETE FROM cuadre_caja WHERE id = %s', (id,))
            conn.commit()
            return cursor.rowcount
        except mysql.connector.Error:
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()
