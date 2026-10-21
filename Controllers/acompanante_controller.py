"""
Acompañantes de una reserva.

Nota importante para el frontend: la tabla `acompanantes_reserva` **no existía
en la base de datos**, así que todos estos endpoints respondían 500. La crea
`migrations/001_backend_spec.sql`.

§6.6 — Cada alta o baja de acompañante recalcula `num_adultos` / `num_ninos`
de la reserva en el servidor, así que el frontend ya no tiene que hacer el
`PATCH /reservas/:id/personas` con los números que él mismo derivaba.
"""
from flask import request

from Models.acompanante_model import AcompananteModel
from Models.reserva_model import ReservaModel
from utils import respuestas
from utils.decorators import requiere_permiso
from utils.validacion import filtrar, fusionar

model = AcompananteModel()
reserva_model = ReservaModel()

CAMPOS = ('tipo_documento', 'numero_documento', 'nombre', 'apellido',
          'telefono', 'es_menor')

OBLIGATORIOS = ('numero_documento', 'nombre', 'apellido')

TIPOS_DOC_VALIDOS = ('CC', 'CE', 'Pasaporte', 'NIT', 'TI', 'RC', 'Otro')


def _validar(data):
    """Devuelve un mensaje de error, o None si el payload está bien."""
    tipo_doc = data.get('tipo_documento', 'CC')
    if tipo_doc not in TIPOS_DOC_VALIDOS:
        return f'tipo_documento debe ser uno de: {list(TIPOS_DOC_VALIDOS)}'
    return None


@requiere_permiso('reservas.ver')
def get_acompanantes_reserva(reserva_id):
    return respuestas.lista(model.get_by_reserva(reserva_id))


@requiere_permiso('reservas.editar')
def create_acompanante(reserva_id):
    data, faltantes = filtrar(request.json, CAMPOS, obligatorios=OBLIGATORIOS)
    if faltantes:
        return respuestas.error(
            f"Faltan campos requeridos: {', '.join(faltantes)}", 400,
            codigo='CAMPOS_REQUERIDOS', campos=faltantes)

    error = _validar(data)
    if error:
        return respuestas.error(error, 400, codigo='VALIDACION')

    try:
        nuevo_id = model.create(reserva_id, data)
    except Exception as exc:
        if 'Duplicate entry' in str(exc) or '1062' in str(exc):
            return respuestas.error(
                'Este documento ya está registrado como acompañante en esta reserva',
                409, codigo='ACOMPANANTE_DUPLICADO')
        raise

    personas = reserva_model.sincronizar_personas(reserva_id)
    return respuestas.creado(model.get_by_id(nuevo_id),
                             mensaje='Acompañante registrado', **personas)


@requiere_permiso('reservas.editar')
def create_acompanantes_bulk(reserva_id):
    lista = request.json
    if not isinstance(lista, list):
        return respuestas.error('Se esperaba una lista de acompañantes', 400,
                                codigo='VALIDACION')
    if not lista:
        return respuestas.lista([], insertados=0)

    limpios = []
    for i, item in enumerate(lista):
        data, faltantes = filtrar(item, CAMPOS, obligatorios=OBLIGATORIOS)
        if faltantes:
            return respuestas.error(
                f"Acompañante #{i + 1}: faltan {', '.join(faltantes)}", 400,
                codigo='CAMPOS_REQUERIDOS')
        error = _validar(data)
        if error:
            return respuestas.error(f'Acompañante #{i + 1}: {error}', 400,
                                    codigo='VALIDACION')
        limpios.append(data)

    insertados = model.create_bulk(reserva_id, limpios)
    personas = reserva_model.sincronizar_personas(reserva_id)

    return respuestas.lista(model.get_by_reserva(reserva_id),
                            insertados=insertados,
                            mensaje=f'{insertados} acompañante(s) registrado(s)',
                            **personas)


@requiere_permiso('reservas.editar')
def update_acompanante(id):
    data, _ = filtrar(request.json, CAMPOS)
    if not data:
        return respuestas.error('No se envió ningún campo editable', 400,
                                codigo='SIN_CAMBIOS')

    error = _validar(data)
    if error:
        return respuestas.error(error, 400, codigo='VALIDACION')

    actual = model.get_by_id(id)
    if not actual:
        return respuestas.error('Acompañante no encontrado', 404,
                                codigo='NO_ENCONTRADO')

    model.update(id, fusionar(actual, data, CAMPOS))
    personas = reserva_model.sincronizar_personas(actual['reserva_id'])

    return respuestas.recurso(model.get_by_id(id),
                              mensaje='Acompañante actualizado', **personas)


@requiere_permiso('reservas.editar')
def delete_acompanante(id):
    actual = model.get_by_id(id)
    if not actual:
        return respuestas.error('Acompañante no encontrado', 404,
                                codigo='NO_ENCONTRADO')

    model.delete(id)
    personas = reserva_model.sincronizar_personas(actual['reserva_id'])

    return respuestas.recurso(None, mensaje='Acompañante eliminado', **personas)
