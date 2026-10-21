"""
§4.1 — La fórmula única del saldo.

Antes el navegador tenía DOS fórmulas para lo mismo y cobraba una u otra según
la pantalla desde la que se llegara a Caja:

    ModalHabitacion.jsx:      max(total + consumos - anticipo, 0)
    CheckOut.jsx / Caja.jsx:  max(total - anticipo, 0) + consumos

Con total=100.000, anticipo=150.000 y consumos=50.000 una pantalla cobraba $0 y
la otra $50.000.

La fórmula que manda, y que vive SÓLO aquí, es:

    total_cuenta    = total_reserva + consumos_pendientes
    saldo_pendiente = max(total_cuenta - anticipo - pagos_registrados, 0)

El anticipo se aplica contra la cuenta completa del huésped, no sólo contra el
alojamiento: es la práctica hotelera habitual, el depósito cubre la factura
entera. (Confirmado como la decisión correcta al implementar el backend.)

`consumos_pendientes` son los consumos cuyo estado NO es 'cancelado'; un
consumo 'cancelado' ya fue cubierto por un pago y por eso sale del saldo.
Los pagos anulados no cuentan.
"""
from decimal import Decimal

CERO = Decimal('0.00')

# Bloque SQL reutilizable: los cuatro agregados que definen el estado
# financiero de una reserva. Se inyecta como subconsultas correlacionadas para
# poder usarlo igual en un listado que en una reserva suelta.
#
# `{r}` es el alias de la tabla `reservas` en la consulta que lo incorpora.
SQL_AGREGADOS = """
    COALESCE((
        SELECT SUM(c.total)
        FROM consumos c
        JOIN reserva_habitaciones rh ON rh.id = c.reserva_habitacion_id
        WHERE rh.reserva_id = {r}.id
          AND c.estado <> 'cancelado'
    ), 0) AS total_consumos,
    COALESCE((
        SELECT SUM(c.total)
        FROM consumos c
        JOIN reserva_habitaciones rh ON rh.id = c.reserva_habitacion_id
        WHERE rh.reserva_id = {r}.id
          AND c.estado = 'cancelado'
    ), 0) AS total_consumos_pagados,
    COALESCE((
        SELECT SUM(p.monto)
        FROM pagos p
        WHERE p.reserva_id = {r}.id
          AND p.anulado = 0
    ), 0) AS total_pagado,
    DATEDIFF({r}.fecha_salida, {r}.fecha_entrada) AS noches
"""


def agregados(alias='r'):
    """El bloque SQL de arriba, con el alias de `reservas` que corresponda."""
    return SQL_AGREGADOS.format(r=alias)


def _dec(valor):
    if valor is None:
        return CERO
    if isinstance(valor, Decimal):
        return valor
    return Decimal(str(valor))


def resumen(fila):
    """
    Recibe una fila de `reservas` que ya trae los agregados de `agregados()` y
    le añade, en el sitio, el resumen financiero que consume el frontend:

        total, anticipo, total_consumos, total_pagado,
        total_cuenta, saldo_pendiente, estado_pago, noches

    Es la ÚNICA función que decide si una reserva está pagada.
    """
    if not fila:
        return fila

    total      = _dec(fila.get('total'))
    anticipo   = _dec(fila.get('anticipo'))
    consumos   = _dec(fila.get('total_consumos'))
    pagado     = _dec(fila.get('total_pagado'))

    total_cuenta = total + consumos
    saldo = total_cuenta - anticipo - pagado
    if saldo < CERO:
        saldo = CERO

    fila['total']           = total
    fila['anticipo']        = anticipo
    fila['total_consumos']  = consumos
    fila['total_pagado']    = pagado
    fila['total_cuenta']    = total_cuenta
    fila['saldo_pendiente'] = saldo
    fila['estado_pago']     = _estado_pago(saldo, anticipo, pagado)

    if fila.get('noches') is None:
        fila['noches'] = 0
    else:
        fila['noches'] = max(int(fila['noches']), 0)

    return fila


def _estado_pago(saldo, anticipo, pagado):
    """
    'pagada'    -> no queda nada por cobrar.
    'parcial'   -> ya entró dinero (anticipo o pagos) pero falta.
    'pendiente' -> no ha entrado nada.

    F11: una reserva cubierta al 100 % por el anticipo sale 'pagada'. Antes el
    frontend exigía además que existiera al menos un pago registrado, así que
    esas reservas quedaban impagas para siempre y "Ir a Caja" ofrecía registrar
    un pago de $0.
    """
    if saldo <= CERO:
        return 'pagada'
    if (anticipo + pagado) > CERO:
        return 'parcial'
    return 'pendiente'


def resumen_lista(filas):
    """Aplica `resumen()` a cada fila de un listado."""
    return [resumen(f) for f in (filas or [])]


def calcular_saldo(cursor, reserva_id, bloquear=False):
    """
    Calcula el saldo de UNA reserva usando un cursor ya abierto, para poder
    hacerlo dentro de la transacción que va a cobrar.

    Con `bloquear=True` hace `SELECT ... FOR UPDATE` sobre la reserva, que es
    lo que impide que dos cajeros simultáneos cobren dos veces el mismo saldo
    (§4.2 regla 5).

    Devuelve el dict de resumen, o None si la reserva no existe.
    """
    cursor.execute(
        f"""
        SELECT r.id, r.estado, r.total, r.anticipo,
               r.fecha_entrada, r.fecha_salida,
               {agregados('r')}
        FROM reservas r
        WHERE r.id = %s
        {'FOR UPDATE' if bloquear else ''}
        """,
        (reserva_id,),
    )
    fila = cursor.fetchone()
    if not fila:
        return None
    return resumen(dict(fila))
