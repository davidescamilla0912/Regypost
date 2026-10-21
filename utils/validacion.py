"""
§5.2 — Allowlist de campos (Mass Assignment) y validación de importes.

Varias pantallas envían el objeto de formulario entero al servidor. Sin una
lista explícita de campos aceptados, un `Modelo(**request.json)` deja que el
cliente escriba `estado`, `total`, `saldo_pendiente` o `rol_id`.

La regla aquí es: cada endpoint declara qué acepta; todo lo demás se descarta.
"""
from decimal import Decimal, InvalidOperation

# Campos que NUNCA se aceptan del cliente, en ningún endpoint. Son el resultado
# de una decisión del servidor, no una entrada del usuario.
CAMPOS_PROHIBIDOS = frozenset({
    'estado', 'estado_pago', 'total', 'saldo_pendiente', 'total_consumos',
    'total_pagado', 'anticipo', 'empleado_id', 'activo', 'rol_id',
    'creado_en', 'noches', 'total_movimiento', 'anulado', 'anulado_por',
    'anulado_en', 'pago_id',
})


def filtrar(data, permitidos, *, obligatorios=()):
    """
    Devuelve `(limpio, faltantes)`.

    `limpio` contiene sólo las claves de `permitidos` presentes en `data`.
    `faltantes` lista los `obligatorios` que no llegaron o llegaron vacíos.

    Un campo de `permitidos` puede estar en CAMPOS_PROHIBIDOS: la allowlist del
    endpoint manda, porque hay casos legítimos (`/confirmar` sí recibe
    `anticipo`). Lo que no puede pasar es que un campo entre sin declararse.
    """
    data = data or {}
    limpio = {k: v for k, v in data.items() if k in permitidos}

    faltantes = [
        campo for campo in obligatorios
        if limpio.get(campo) is None
        or (isinstance(limpio.get(campo), str) and not limpio[campo].strip())
    ]
    return limpio, faltantes


def descartados(data, permitidos):
    """Claves que el cliente envió y el endpoint ignoró. Útil para avisar."""
    return sorted(set((data or {}).keys()) - set(permitidos))


def a_decimal(valor, *, campo='valor', minimo=None, maximo=None,
              permite_none=False):
    """
    Convierte a Decimal validando rango. Lanza ValueError con un mensaje
    legible para el usuario final (no un traceback).
    """
    if valor is None or valor == '':
        if permite_none:
            return None
        raise ValueError(f'{campo} es requerido')

    try:
        numero = Decimal(str(valor).strip())
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError(f'{campo} debe ser un número válido')

    if not numero.is_finite():
        raise ValueError(f'{campo} debe ser un número válido')
    if minimo is not None and numero < minimo:
        raise ValueError(f'{campo} no puede ser menor que {minimo}')
    if maximo is not None and numero > maximo:
        raise ValueError(f'{campo} no puede ser mayor que {maximo}')
    return numero


def a_entero(valor, *, campo='valor', minimo=None, maximo=None,
             permite_none=False):
    """Convierte a int validando rango, con el mismo criterio que a_decimal."""
    if valor is None or valor == '':
        if permite_none:
            return None
        raise ValueError(f'{campo} es requerido')

    try:
        numero = int(str(valor).strip())
    except (TypeError, ValueError):
        raise ValueError(f'{campo} debe ser un número entero')

    if minimo is not None and numero < minimo:
        raise ValueError(f'{campo} no puede ser menor que {minimo}')
    if maximo is not None and numero > maximo:
        raise ValueError(f'{campo} no puede ser mayor que {maximo}')
    return numero


def fusionar(actual, cambios, permitidos):
    """
    Mezcla los campos que llegaron sobre los que ya tiene el registro.

    Varios modelos escriben la fila completa en su UPDATE, así que un PUT
    parcial les llegaría con claves ausentes. Esto conserva la semántica de
    "actualiza sólo lo que mandaste" sin tener que reescribir cada modelo.
    """
    base = {campo: actual[campo] for campo in permitidos if campo in (actual or {})}
    base.update(cambios or {})
    return base
