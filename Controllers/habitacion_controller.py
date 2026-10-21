from flask import request

from Models.habitacion_model import HabitacionModel
from Models.reserva_model import TransicionInvalida
from utils import respuestas
from utils.decorators import requiere_permiso, tiene_permiso
from utils.validacion import descartados, filtrar

model = HabitacionModel()

ESTADOS_VALIDOS = ['disponible', 'reservada', 'ocupada', 'mantenimiento',
                   'bloqueada']

CAMPOS_HABITACION = ('numero', 'piso', 'tipo_id', 'tipo_cama',
                     'notas_mantenimiento')


@requiere_permiso('habitaciones.ver')
def get_all_habitaciones():
    return respuestas.lista(model.get_all())


@requiere_permiso('habitaciones.ver')
def get_habitacion(id):
    habitacion = model.get_by_id(id)
    if not habitacion:
        return respuestas.error('Habitación no encontrada', 404,
                                codigo='NO_ENCONTRADO')
    return respuestas.recurso(habitacion)


@requiere_permiso('habitaciones.ver')
def get_habitaciones_disponibles():
    """
    §6.2 — `GET /habitaciones/disponibles?desde=YYYY-MM-DD&hasta=YYYY-MM-DD`

    Con fechas devuelve la disponibilidad real del rango, calculada con la
    misma regla de solapamiento que aplica el alta de reservas. Sin fechas,
    las que están libres ahora mismo.
    """
    try:
        filas = model.get_disponibles(request.args.get('desde'),
                                      request.args.get('hasta'))
    except ValueError as exc:
        mensaje = ('La fecha "hasta" debe ser posterior a "desde"'
                   if str(exc) == 'fechas_invalidas' else str(exc))
        return respuestas.error(mensaje, 400, codigo='FECHAS_INVALIDAS')

    return respuestas.lista(filas, desde=request.args.get('desde'),
                            hasta=request.args.get('hasta'))


@requiere_permiso('habitaciones.ver')
def get_habitaciones_by_estado(estado):
    if estado not in ESTADOS_VALIDOS:
        return respuestas.error(f'Estado debe ser uno de: {ESTADOS_VALIDOS}',
                                400, codigo='ESTADO_INVALIDO')
    return respuestas.lista(model.get_by_estado(estado))


@requiere_permiso('habitaciones.editar')
def create_habitacion():
    data, faltantes = filtrar(
        request.json, CAMPOS_HABITACION + ('estado',),
        obligatorios=('numero', 'piso', 'tipo_id'),
    )
    if faltantes:
        return respuestas.error(
            f"Faltan campos requeridos: {', '.join(faltantes)}", 400,
            codigo='CAMPOS_REQUERIDOS', campos=faltantes)

    if data.get('estado') and data['estado'] not in ESTADOS_VALIDOS:
        return respuestas.error(f'Estado debe ser uno de: {ESTADOS_VALIDOS}',
                                400, codigo='ESTADO_INVALIDO')

    nuevo_id = model.create(data)
    return respuestas.creado(model.get_by_id(nuevo_id),
                             mensaje='Habitación creada')


@requiere_permiso('habitaciones.editar')
def update_habitacion(id):
    """
    Edita los datos de la habitación. `estado` NO se acepta aquí: tiene su
    propio endpoint, que valida la máquina de estados.
    """
    data, _ = filtrar(request.json, CAMPOS_HABITACION)
    if not data:
        return respuestas.error('No se envió ningún campo editable', 400,
                                codigo='SIN_CAMBIOS',
                                campos_editables=list(CAMPOS_HABITACION))

    afectadas = model.update(id, data)
    if not afectadas:
        return respuestas.error('Habitación no encontrada', 404,
                                codigo='NO_ENCONTRADO')

    return respuestas.recurso(model.get_by_id(id),
                              mensaje='Habitación actualizada',
                              ignorados=descartados(request.json,
                                                    CAMPOS_HABITACION))


@requiere_permiso('habitaciones.editar')
def update_estado_habitacion(id):
    """
    §6.3 — Valida la transición.

    Ya no se puede pasar de 'ocupada' a 'disponible' con el huésped dentro
    (F29). Y si se pide 'disponible' pero la habitación tiene reservas
    activas, el servidor deja 'reservada' en un solo PATCH, en vez de que el
    cliente lo resuelva en dos pasos (F28).
    """
    data = request.json or {}
    estado = data.get('estado')

    if estado not in ESTADOS_VALIDOS:
        return respuestas.error(f'Estado debe ser uno de: {ESTADOS_VALIDOS}',
                                400, codigo='ESTADO_INVALIDO')

    forzar = bool(data.get('forzar')) and tiene_permiso('reservas.forzar_estado')

    try:
        afectadas, estado_final = model.update_estado(id, estado, forzar=forzar)
    except TransicionInvalida as exc:
        return respuestas.error(
            f'No se puede pasar de "{exc.desde}" a "{exc.hacia}"', 409,
            codigo='TRANSICION_INVALIDA', estado_actual=exc.desde,
            transiciones_permitidas=exc.permitidas)

    if not afectadas:
        return respuestas.error('Habitación no encontrada', 404,
                                codigo='NO_ENCONTRADO')

    mensaje = f'Estado actualizado a {estado_final}'
    if estado_final != estado:
        mensaje += (f' (se pidió "{estado}", pero la habitación tiene '
                    f'reservas activas)')

    return respuestas.recurso(model.get_by_id(id), mensaje=mensaje,
                              estado_solicitado=estado,
                              estado_final=estado_final)


@requiere_permiso('habitaciones.editar')
def delete_habitacion(id):
    afectadas = model.delete(id)
    if not afectadas:
        return respuestas.error('Habitación no encontrada', 404,
                                codigo='NO_ENCONTRADO')
    return respuestas.sin_contenido('Habitación eliminada')
