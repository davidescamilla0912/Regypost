from flask import request

from Models.reserva_model import (
    ESTADOS_BLOQUEAN, ReservaModel, TransicionInvalida, normalizar_estado,
)
from utils import respuestas
from utils.decorators import (
    empleado_actual_id, requiere_permiso, tiene_permiso,
)
from utils.validacion import a_decimal, a_entero, descartados, filtrar

model = ReservaModel()

ESTADOS_VALIDOS = ['pendiente', 'confirmada', 'checkin', 'checkout', 'cancelada']

# §5.2 — Allowlist: lo que un cliente puede escribir al crear una reserva.
# `total`, `noches`, `saldo_pendiente` y `estado` NO están, y por eso el
# payload duplicado que enviaba el frontend (total/valor_total, check_in/
# fecha_entrada...) se descarta solo.
CAMPOS_CREAR = (
    'cliente_id', 'habitacion_id', 'fecha_entrada', 'fecha_salida',
    'fecha_reserva', 'hora_llegada', 'hora_salida', 'precio_noche',
    'num_adultos', 'num_ninos', 'fuente', 'observaciones', 'acompanantes',
)

CAMPOS_EDITAR = (
    'cliente_id', 'fecha_entrada', 'fecha_salida', 'hora_llegada',
    'hora_salida', 'num_adultos', 'num_ninos', 'fuente', 'late_checkout',
    'observaciones',
)

# Mensajes de los errores de validación que levanta el modelo.
ERRORES_MODELO = {
    'fechas_invalidas': (
        'La fecha de salida debe ser posterior a la de entrada', 400,
        'FECHAS_INVALIDAS'),
    'solapamiento_fechas': (
        'La habitación ya tiene una reserva activa en ese rango de fechas', 409,
        'SOLAPAMIENTO_FECHAS'),
    'habitacion_no_encontrada': ('Habitación no encontrada', 404, 'NO_ENCONTRADO'),
    'cliente_no_encontrado': ('Cliente no encontrado', 404, 'NO_ENCONTRADO'),
    'reserva_no_encontrada': ('Reserva no encontrada', 404, 'NO_ENCONTRADO'),
    'precio_invalido': (
        'El precio por noche debe ser mayor que 0', 400, 'PRECIO_INVALIDO'),
}


def _error_modelo(exc):
    mensaje, status, codigo = ERRORES_MODELO.get(
        str(exc), ('Error de validación', 400, 'VALIDACION'))
    return respuestas.error(mensaje, status, codigo=codigo)


def _error_transicion(exc):
    return respuestas.error(
        f'No se puede pasar de "{exc.desde}" a "{exc.hacia}"',
        409,
        codigo='TRANSICION_INVALIDA',
        estado_actual=exc.desde,
        transiciones_permitidas=exc.permitidas,
    )


# ─── LECTURA ──────────────────────────────────────────────────────────────────
# Todas devuelven ya el resumen financiero (§4.1) y las habitaciones
# embebidas (§8.1).

@requiere_permiso('reservas.ver')
def get_all_reservas():
    return respuestas.lista(model.get_all())


@requiere_permiso('reservas.ver')
def get_reserva(id):
    reserva = model.get_by_id(id)
    if not reserva:
        return respuestas.error('Reserva no encontrada', 404, codigo='NO_ENCONTRADO')
    return respuestas.recurso(reserva)


@requiere_permiso('reservas.ver')
def get_reservas_activas():
    return respuestas.lista(model.get_activas())


@requiere_permiso('reservas.ver')
def get_reservas_by_estado(estado):
    estado = normalizar_estado(estado)
    if estado not in ESTADOS_VALIDOS:
        return respuestas.error(
            f'Estado debe ser uno de: {ESTADOS_VALIDOS}', 400,
            codigo='ESTADO_INVALIDO')
    return respuestas.lista(model.get_by_estado(estado))


# ─── §6.1 ALTA TRANSACCIONAL ──────────────────────────────────────────────────

@requiere_permiso('reservas.crear')
def create_reserva():
    data, faltantes = filtrar(
        request.json, CAMPOS_CREAR,
        obligatorios=('cliente_id', 'fecha_entrada', 'fecha_salida'),
    )
    if faltantes:
        return respuestas.error(
            f"Faltan campos requeridos: {', '.join(faltantes)}", 400,
            codigo='CAMPOS_REQUERIDOS', campos=faltantes)

    try:
        nuevo_id = model.create(data, empleado_id=empleado_actual_id())
    except ValueError as exc:
        return _error_modelo(exc)

    return respuestas.creado(
        model.get_by_id(nuevo_id),
        mensaje='Reserva creada',
        ignorados=descartados(request.json, CAMPOS_CREAR),
    )


@requiere_permiso('reservas.editar')
def update_reserva(id):
    """
    §5.2 — Sólo se escriben los campos de la allowlist. `{"total": 1}` se
    ignora en silencio y se informa en `ignorados`.
    """
    data, _ = filtrar(request.json, CAMPOS_EDITAR)
    if not data:
        return respuestas.error(
            'No se envió ningún campo editable', 400, codigo='SIN_CAMBIOS',
            campos_editables=list(CAMPOS_EDITAR))

    try:
        afectadas = model.update(id, data)
    except ValueError as exc:
        return _error_modelo(exc)

    if not afectadas:
        return respuestas.error('Reserva no encontrada', 404, codigo='NO_ENCONTRADO')

    return respuestas.recurso(
        model.get_by_id(id),
        mensaje='Reserva actualizada',
        ignorados=descartados(request.json, CAMPOS_EDITAR),
    )


# ─── §6.3 ESTADOS ─────────────────────────────────────────────────────────────

@requiere_permiso('reservas.editar')
def update_estado_reserva(id):
    """
    Cambia el estado respetando la máquina de estados. Para check-in y
    check-out conviene usar los endpoints dedicados (§6.4), que además mueven
    las habitaciones y validan el saldo.
    """
    data = request.json or {}
    estado = normalizar_estado(data.get('estado'))

    if estado not in ESTADOS_VALIDOS:
        return respuestas.error(
            f'Estado debe ser uno de: {ESTADOS_VALIDOS}', 400,
            codigo='ESTADO_INVALIDO')

    forzar = bool(data.get('forzar')) and tiene_permiso('reservas.forzar_estado')

    try:
        afectadas = model.update_estado(id, estado, forzar=forzar)
    except TransicionInvalida as exc:
        return _error_transicion(exc)

    if not afectadas:
        return respuestas.error('Reserva no encontrada', 404, codigo='NO_ENCONTRADO')

    return respuestas.recurso(model.get_by_id(id),
                              mensaje=f'Estado actualizado a {estado}')


@requiere_permiso('reservas.editar')
def confirmar_reserva(id):
    data = request.json or {}

    try:
        anticipo = a_decimal(data.get('anticipo'), campo='anticipo', minimo=0)
    except ValueError as exc:
        return respuestas.error(str(exc), 400, codigo='VALIDACION')

    reserva_actual = model.get_by_id(id)
    if not reserva_actual:
        return respuestas.error('Reserva no encontrada', 404, codigo='NO_ENCONTRADO')

    total = reserva_actual.get('total') or 0
    if anticipo > total:
        return respuestas.error(
            'El anticipo no puede ser mayor que el total de la reserva', 400,
            codigo='ANTICIPO_EXCEDE_TOTAL', total=total)

    reserva, estado = model.confirmar_reserva(id, anticipo)

    if estado == 'not_found':
        return respuestas.error('Reserva no encontrada', 404, codigo='NO_ENCONTRADO')
    if estado == 'invalid_state':
        return respuestas.error(
            'Solo se puede confirmar una reserva en estado pendiente', 409,
            codigo='TRANSICION_INVALIDA')

    return respuestas.recurso(reserva, mensaje='Reserva confirmada')


# ─── §6.4 CHECK-IN / CHECK-OUT ATÓMICOS ───────────────────────────────────────

@requiere_permiso('checkin.hacer')
def checkin_reserva(id):
    """
    POST /reservas/<id>/checkin — una sola llamada, una sola transacción.
    Cambia la reserva a 'checkin' y sus habitaciones a 'ocupada'.
    """
    reserva, estado = model.checkin(id, empleado_id=empleado_actual_id())

    errores = {
        'not_found': ('Reserva no encontrada', 404, 'NO_ENCONTRADO'),
        'invalid_state': (
            'Solo se puede hacer check-in de una reserva confirmada', 409,
            'TRANSICION_INVALIDA'),
        'fecha_futura': (
            'La fecha de entrada todavía no ha llegado', 409, 'FECHA_FUTURA'),
        'habitacion_ocupada': (
            'La habitación tiene otro check-in sin cerrar', 409,
            'HABITACION_OCUPADA'),
        'sin_habitacion': (
            'La reserva no tiene ninguna habitación asignada', 409,
            'SIN_HABITACION'),
    }
    if estado in errores:
        mensaje, status, codigo = errores[estado]
        return respuestas.error(mensaje, status, codigo=codigo)

    return respuestas.recurso(reserva, mensaje='Check-in realizado')


@requiere_permiso('checkout.hacer')
def checkout_reserva(id):
    """
    POST /reservas/<id>/checkout — cierra la reserva y manda TODAS sus
    habitaciones a mantenimiento en la misma transacción.

    Con saldo pendiente responde 409. Sólo quien tenga `checkout.forzar` puede
    enviar `{"forzar": true, "motivo": "..."}`, y queda registrado.
    """
    data = request.json or {}
    quiere_forzar = bool(data.get('forzar'))
    puede_forzar = tiene_permiso('checkout.forzar')

    if quiere_forzar and not puede_forzar:
        return respuestas.error(
            'No tienes permiso para forzar un check-out con saldo pendiente',
            403, codigo='PERMISO_DENEGADO', permiso='checkout.forzar')

    reserva, estado, saldo = model.checkout(
        id,
        empleado_id=empleado_actual_id(),
        forzar=quiere_forzar and puede_forzar,
        motivo=data.get('motivo'),
    )

    if estado == 'not_found':
        return respuestas.error('Reserva no encontrada', 404, codigo='NO_ENCONTRADO')
    if estado == 'invalid_state':
        return respuestas.error(
            'Solo se puede hacer check-out de una reserva en check-in', 409,
            codigo='TRANSICION_INVALIDA')
    if estado == 'saldo_pendiente':
        return respuestas.error(
            f'La reserva tiene un saldo pendiente de ${saldo:,.2f}', 409,
            codigo='SALDO_PENDIENTE', saldo_pendiente=saldo,
            puede_forzar=puede_forzar)

    mensaje = ('Check-out realizado (forzado con saldo pendiente)'
               if saldo and saldo > 0 else 'Check-out realizado')
    return respuestas.recurso(reserva, mensaje=mensaje)


@requiere_permiso('reservas.cancelar')
def cancelar_reserva(id):
    """
    POST /reservas/<id>/cancelar — F25: si hay pagos registrados o el check-in
    ya se hizo, exige `forzar: true` y un motivo.
    """
    data = request.json or {}
    motivo = (data.get('motivo') or '').strip()
    quiere_forzar = bool(data.get('forzar'))
    puede_forzar = tiene_permiso('reservas.forzar_estado')

    reserva, estado = model.cancelar(
        id,
        motivo=motivo,
        empleado_id=empleado_actual_id(),
        forzar=quiere_forzar and puede_forzar and bool(motivo),
    )

    if estado == 'not_found':
        return respuestas.error('Reserva no encontrada', 404, codigo='NO_ENCONTRADO')
    if estado == 'invalid_state':
        return respuestas.error(
            'La reserva ya está cancelada o cerrada', 409,
            codigo='TRANSICION_INVALIDA')
    if estado == 'tiene_pagos':
        return respuestas.error(
            'La reserva tiene pagos registrados o el huésped ya hizo check-in. '
            'Se requiere confirmación explícita con un motivo.',
            409, codigo='CANCELACION_REQUIERE_MOTIVO',
            puede_forzar=puede_forzar)

    return respuestas.recurso(reserva, mensaje='Reserva cancelada')


@requiere_permiso('reservas.cancelar')
def delete_reserva(id):
    afectadas = model.delete(id)
    if not afectadas:
        return respuestas.error('Reserva no encontrada', 404, codigo='NO_ENCONTRADO')
    return respuestas.sin_contenido('Reserva eliminada')


# ─── HABITACIONES DE LA RESERVA ───────────────────────────────────────────────

@requiere_permiso('reservas.ver')
def get_habitaciones_reserva(reserva_id):
    return respuestas.lista(model.get_habitaciones(reserva_id))


@requiere_permiso('reservas.crear')
def agregar_habitacion_reserva(reserva_id):
    data, faltantes = filtrar(
        request.json, ('habitacion_id', 'precio_noche'),
        obligatorios=('habitacion_id',),
    )
    if faltantes:
        return respuestas.error('habitacion_id es requerido', 400,
                                codigo='CAMPOS_REQUERIDOS')

    try:
        model.agregar_habitacion(reserva_id, data)
    except ValueError as exc:
        return _error_modelo(exc)

    return respuestas.creado(model.get_by_id(reserva_id),
                             mensaje='Habitación agregada a la reserva')


@requiere_permiso('reservas.editar')
def quitar_habitacion_reserva(reserva_id, habitacion_id):
    model.quitar_habitacion(reserva_id, habitacion_id)
    return respuestas.recurso(model.get_by_id(reserva_id),
                              mensaje='Habitación removida de la reserva')


@requiere_permiso('reservas.ver')
def get_reservas_futuras_habitacion(habitacion_id):
    return respuestas.recurso(
        {'tiene_reservas_futuras': model.tiene_reservas_futuras(habitacion_id)}
    )


# ─── §6.5 EXTENSIÓN ───────────────────────────────────────────────────────────

@requiere_permiso('reservas.editar')
def extender_reserva(id):
    data = request.json or {}

    try:
        dias_extra = a_entero(data.get('dias_extra'), campo='dias_extra',
                              minimo=1, maximo=365)
        precio_noche = a_decimal(data.get('precio_noche'), campo='precio_noche',
                                 minimo=0, permite_none=True)
    except ValueError as exc:
        return respuestas.error(str(exc), 400, codigo='VALIDACION')

    if precio_noche is not None and precio_noche <= 0:
        return respuestas.error('precio_noche debe ser mayor que 0', 400,
                                codigo='VALIDACION')

    resultado, estado = model.extender_dias(
        id, dias_extra,
        precio_noche_override=float(precio_noche) if precio_noche is not None else None,
        permite_precio_especial=tiene_permiso('reservas.precio_especial'),
    )

    errores = {
        'not_found': ('Reserva no encontrada', 404, 'NO_ENCONTRADO'),
        'invalid_state': (
            'Solo se pueden extender reservas en estado check-in', 409,
            'TRANSICION_INVALIDA'),
        'invalid_date': ('La reserva no tiene fecha de salida', 400, 'VALIDACION'),
        'missing_price': (
            'La reserva no tiene un precio por noche registrado', 400,
            'PRECIO_REQUERIDO'),
        'date_conflict': (
            'La extensión choca con una reserva futura en esa habitación', 409,
            'SOLAPAMIENTO_FECHAS'),
    }
    if estado in errores:
        mensaje, status, codigo = errores[estado]
        return respuestas.error(mensaje, status, codigo=codigo)

    if estado == 'precio_fuera_de_rango':
        return respuestas.error(
            'El precio por noche se aleja demasiado del pactado. '
            'Se requiere el permiso reservas.precio_especial.',
            422, codigo='PRECIO_FUERA_DE_RANGO', **resultado)

    return respuestas.recurso(resultado, mensaje='Estadía extendida')


# ─── CAMBIO DE HABITACIÓN ─────────────────────────────────────────────────────

@requiere_permiso('reservas.editar')
def cambiar_habitacion(id):
    data = request.json or {}
    nueva_habitacion_id = data.get('nueva_habitacion_id')
    motivo = (data.get('motivo') or '').strip()

    try:
        nueva_habitacion_id = a_entero(nueva_habitacion_id,
                                       campo='nueva_habitacion_id', minimo=1)
    except ValueError as exc:
        return respuestas.error(str(exc), 400, codigo='VALIDACION')

    if not motivo:
        return respuestas.error('motivo es requerido', 400,
                                codigo='CAMPOS_REQUERIDOS')
    if len(motivo) > 500:
        return respuestas.error('motivo no puede superar 500 caracteres', 400,
                                codigo='VALIDACION')

    resultado, estado = model.cambiar_habitacion(
        reserva_id=id,
        nueva_habitacion_id=nueva_habitacion_id,
        motivo=motivo,
        empleado_id=empleado_actual_id(),
    )

    errores = {
        'not_found': ('Reserva no encontrada', 404, 'NO_ENCONTRADO'),
        'invalid_state': (
            'Solo se puede cambiar la habitación de una reserva en check-in',
            409, 'TRANSICION_INVALIDA'),
        'no_room_linked': ('La reserva no tiene habitación asignada', 409,
                           'SIN_HABITACION'),
        'same_room': ('La habitación destino es la misma que la actual', 400,
                      'VALIDACION'),
        'dest_not_found': ('Habitación destino no encontrada', 404,
                           'NO_ENCONTRADO'),
        'dest_not_available': (
            'La habitación destino no está disponible', 409, 'HABITACION_OCUPADA'),
        'date_conflict': (
            'La habitación destino tiene una reserva que choca con esta estadía',
            409, 'SOLAPAMIENTO_FECHAS'),
    }
    if estado in errores:
        mensaje, status, codigo = errores[estado]
        return respuestas.error(mensaje, status, codigo=codigo)

    return respuestas.recurso(resultado, mensaje='Habitación cambiada')


@requiere_permiso('reservas.ver')
def get_habitaciones_para_cambio(id):
    return respuestas.lista(model.get_habitaciones_para_cambio(id))


# ─── §6.6 NÚMERO DE HUÉSPEDES ─────────────────────────────────────────────────

@requiere_permiso('reservas.editar')
def update_personas_reserva(id):
    """
    Recalcula `num_adultos` / `num_ninos` desde la tabla de acompañantes.

    Ya no acepta los números del cliente: los derivaba el navegador a partir
    de la misma lista y había dos fuentes de verdad para el mismo campo (F30).
    Si la reserva no tiene acompañantes registrados nominalmente, se acepta lo
    que envíe el cliente como respaldo.
    """
    data = request.json or {}
    reserva = model.get_by_id(id)
    if not reserva:
        return respuestas.error('Reserva no encontrada', 404, codigo='NO_ENCONTRADO')

    personas = model.sincronizar_personas(id)

    # Sin acompañantes registrados no hay nada que derivar: vale lo tecleado.
    if personas['num_adultos'] == 1 and personas['num_ninos'] == 0 \
            and data.get('num_adultos') is not None:
        try:
            adultos = a_entero(data.get('num_adultos'), campo='num_adultos',
                               minimo=1, maximo=20)
            ninos = a_entero(data.get('num_ninos', 0), campo='num_ninos',
                             minimo=0, maximo=20)
        except ValueError as exc:
            return respuestas.error(str(exc), 400, codigo='VALIDACION')

        model.update(id, {'num_adultos': adultos, 'num_ninos': ninos})
        personas = {'num_adultos': adultos, 'num_ninos': ninos}

    return respuestas.recurso(model.get_by_id(id), **personas)
