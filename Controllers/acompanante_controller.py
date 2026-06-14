from flask import request, jsonify
from Models.acompanante_model import AcompananteModel
from utils.decorators import requiere_permiso

model = AcompananteModel()

# ─── Campos requeridos para crear / actualizar ────────────────────────────────
CAMPOS_REQUERIDOS = ('numero_documento', 'nombre', 'apellido')

TIPOS_DOC_VALIDOS = ('CC', 'CE', 'Pasaporte', 'NIT', 'Otro')


def _validar_payload(data):
    """
    Valida que el payload tenga los campos mínimos.
    Retorna un mensaje de error o None si todo está bien.
    """
    if not data:
        return 'Se requiere un cuerpo JSON'

    for campo in CAMPOS_REQUERIDOS:
        if not data.get(campo) or not str(data[campo]).strip():
            return f'{campo} es requerido'

    tipo_doc = data.get('tipo_documento', 'CC')
    if tipo_doc not in TIPOS_DOC_VALIDOS:
        return f'tipo_documento debe ser uno de: {list(TIPOS_DOC_VALIDOS)}'

    return None


# ─── GET /reservas/<reserva_id>/acompanantes ─────────────────────────────────
@requiere_permiso('reservas.ver')
def get_acompanantes_reserva(reserva_id):
    """Lista todos los acompañantes de una reserva."""
    acompanantes = model.get_by_reserva(reserva_id)
    return jsonify(acompanantes), 200


# ─── POST /reservas/<reserva_id>/acompanantes ────────────────────────────────
@requiere_permiso('reservas.editar')
def create_acompanante(reserva_id):
    """Agrega UN acompañante a una reserva existente."""
    data = request.json
    error = _validar_payload(data)
    if error:
        return jsonify({'error': error}), 400

    try:
        new_id = model.create(reserva_id, data)
        acomp = model.get_by_id(new_id)
        return jsonify({
            'mensaje': 'Acompañante registrado correctamente',
            'acompanante': acomp
        }), 201
    except Exception as e:
        # El UNIQUE KEY (reserva_id, numero_documento) puede disparar este error
        msg = str(e)
        if 'Duplicate entry' in msg or '1062' in msg:
            return jsonify({
                'error': 'Este documento ya está registrado como acompañante en esta reserva'
            }), 409
        return jsonify({'error': 'Error interno al registrar el acompañante'}), 500


# ─── POST /reservas/<reserva_id>/acompanantes/bulk ───────────────────────────
@requiere_permiso('reservas.editar')
def create_acompanantes_bulk(reserva_id):
    """
    Agrega VARIOS acompañantes de una sola vez.
    Body esperado: [ { tipo_documento, numero_documento, nombre, apellido, telefono }, ... ]
    """
    data = request.json
    if not isinstance(data, list):
        return jsonify({'error': 'Se esperaba una lista de acompañantes'}), 400

    if len(data) == 0:
        return jsonify({'mensaje': 'No se enviaron acompañantes', 'insertados': 0}), 200

    # Validar cada elemento
    for i, item in enumerate(data):
        error = _validar_payload(item)
        if error:
            return jsonify({'error': f'Acompañante #{i + 1}: {error}'}), 400

    try:
        insertados = model.create_bulk(reserva_id, data)
        acompanantes = model.get_by_reserva(reserva_id)
        return jsonify({
            'mensaje': f'{insertados} acompañante(s) registrado(s)',
            'insertados': insertados,
            'acompanantes': acompanantes
        }), 201
    except Exception as e:
        return jsonify({'error': 'Error interno al registrar los acompañantes'}), 500


# ─── PUT /acompanantes/<id> ───────────────────────────────────────────────────
@requiere_permiso('reservas.editar')
def update_acompanante(id):
    """Edita los datos de un acompañante."""
    data = request.json
    error = _validar_payload(data)
    if error:
        return jsonify({'error': error}), 400

    affected = model.update(id, data)
    if not affected:
        return jsonify({'error': 'Acompañante no encontrado'}), 404

    return jsonify({
        'mensaje': 'Acompañante actualizado',
        'acompanante': model.get_by_id(id)
    }), 200


# ─── DELETE /acompanantes/<id> ────────────────────────────────────────────────
@requiere_permiso('reservas.editar')
def delete_acompanante(id):
    """Elimina un acompañante por su id."""
    affected = model.delete(id)
    if not affected:
        return jsonify({'error': 'Acompañante no encontrado'}), 404

    return jsonify({'mensaje': 'Acompañante eliminado'}), 200
