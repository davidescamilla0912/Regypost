from flask import request
from flask_jwt_extended import jwt_required

from Models.cliente_model import ClienteModel
from utils import respuestas
from utils.decorators import requiere_permiso
from utils.validacion import descartados, filtrar, fusionar

model = ClienteModel()

# §5.2 — `NuevoCliente.jsx` enviaba el objeto de formulario entero.
CAMPOS_CLIENTE = ('tipo_documento', 'numero_documento', 'nombre', 'apellido',
                  'nacionalidad', 'telefono', 'email', 'direccion', 'empresa',
                  'fecha_nacimiento', 'notas')


@jwt_required()
def get_all_clientes():
    return respuestas.lista(model.get_all())


@jwt_required()
def get_cliente(id):
    cliente = model.get_by_id(id)
    if not cliente:
        return respuestas.error('Cliente no encontrado', 404,
                                codigo='NO_ENCONTRADO')
    return respuestas.recurso(cliente)


@jwt_required()
def get_cliente_by_documento(numero_documento):
    cliente = model.get_by_documento(numero_documento)
    if not cliente:
        return respuestas.error('Cliente no encontrado', 404,
                                codigo='NO_ENCONTRADO')
    return respuestas.recurso(cliente)


@requiere_permiso('clientes.crear')
def create_cliente():
    data, faltantes = filtrar(
        request.json, CAMPOS_CLIENTE,
        obligatorios=('numero_documento', 'nombre', 'apellido'),
    )
    if faltantes:
        return respuestas.error(
            f"Faltan campos requeridos: {', '.join(faltantes)}", 400,
            codigo='CAMPOS_REQUERIDOS', campos=faltantes)

    try:
        nuevo_id = model.create(data)
    except Exception as exc:
        if 'Duplicate entry' in str(exc) or '1062' in str(exc):
            return respuestas.error(
                'Ya existe un cliente con ese número de documento', 409,
                codigo='DOCUMENTO_DUPLICADO')
        raise

    return respuestas.creado(model.get_by_id(nuevo_id), mensaje='Cliente creado',
                             ignorados=descartados(request.json, CAMPOS_CLIENTE))


@requiere_permiso('clientes.crear')
def update_cliente(id):
    data, _ = filtrar(request.json, CAMPOS_CLIENTE)
    if not data:
        return respuestas.error('No se envió ningún campo editable', 400,
                                codigo='SIN_CAMBIOS')

    actual = model.get_by_id(id)
    if not actual:
        return respuestas.error('Cliente no encontrado', 404,
                                codigo='NO_ENCONTRADO')

    afectadas = model.update(id, fusionar(actual, data, CAMPOS_CLIENTE))
    if not afectadas:
        return respuestas.error('Cliente no encontrado', 404,
                                codigo='NO_ENCONTRADO')

    return respuestas.recurso(model.get_by_id(id), mensaje='Cliente actualizado',
                              ignorados=descartados(request.json, CAMPOS_CLIENTE))


@requiere_permiso('clientes.crear')
def delete_cliente(id):
    afectadas = model.delete(id)
    if not afectadas:
        return respuestas.error('Cliente no encontrado', 404,
                                codigo='NO_ENCONTRADO')
    return respuestas.sin_contenido('Cliente eliminado')


@jwt_required()
def search_clientes():
    query = request.args.get('q', '')
    if not query:
        return respuestas.error('Parámetro de búsqueda requerido', 400,
                                codigo='CAMPOS_REQUERIDOS')
    return respuestas.lista(model.search(query))
