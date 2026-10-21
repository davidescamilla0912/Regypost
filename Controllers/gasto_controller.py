from flask import request

from Models.gasto_model import GastoModel
from utils import respuestas
from utils.decorators import empleado_actual_id, requiere_permiso
from utils.validacion import a_decimal, descartados, filtrar

model = GastoModel()

CATEGORIAS_VALIDAS = ['olimpica', 'ferreteria', 'turno', 'insumos',
                      'mantenimiento', 'varios']

# §7.4 / F38 — `empleado_id` no se acepta: se tecleaba a mano como un número
# libre. Ahora sale del JWT.
CAMPOS_GASTO = ('fecha', 'categoria', 'descripcion', 'monto')


@requiere_permiso('caja.ver')
def get_all_gastos():
    return respuestas.lista(model.get_all())


@requiere_permiso('caja.ver')
def get_gasto(id):
    gasto = model.get_by_id(id)
    if not gasto:
        return respuestas.error('Gasto no encontrado', 404, codigo='NO_ENCONTRADO')
    return respuestas.recurso(gasto)


@requiere_permiso('caja.ver')
def get_gastos_fecha(fecha):
    return respuestas.lista(model.get_by_fecha(fecha))


@requiere_permiso('caja.ver')
def get_gastos_categoria(categoria):
    if categoria not in CATEGORIAS_VALIDAS:
        return respuestas.error(
            f'Categoría debe ser una de: {CATEGORIAS_VALIDAS}', 400,
            codigo='CATEGORIA_INVALIDA')
    return respuestas.lista(model.get_by_categoria(categoria))


def _validar(data):
    if data.get('categoria') and data['categoria'] not in CATEGORIAS_VALIDAS:
        raise ValueError(f'Categoría debe ser una de: {CATEGORIAS_VALIDAS}')
    a_decimal(data.get('monto'), campo='monto', minimo=0)


@requiere_permiso('caja.crear')
def create_gasto():
    data, faltantes = filtrar(request.json, CAMPOS_GASTO,
                              obligatorios=('fecha', 'monto'))
    if faltantes:
        return respuestas.error(
            f"Faltan campos requeridos: {', '.join(faltantes)}", 400,
            codigo='CAMPOS_REQUERIDOS', campos=faltantes)

    try:
        _validar(data)
    except ValueError as exc:
        return respuestas.error(str(exc), 400, codigo='VALIDACION')

    nuevo_id = model.create(data, empleado_id=empleado_actual_id())
    return respuestas.creado(model.get_by_id(nuevo_id),
                             mensaje='Gasto registrado',
                             ignorados=descartados(request.json, CAMPOS_GASTO))


@requiere_permiso('caja.crear')
def update_gasto(id):
    data, faltantes = filtrar(request.json, CAMPOS_GASTO,
                              obligatorios=('fecha', 'monto'))
    if faltantes:
        return respuestas.error(
            f"Faltan campos requeridos: {', '.join(faltantes)}", 400,
            codigo='CAMPOS_REQUERIDOS', campos=faltantes)

    try:
        _validar(data)
    except ValueError as exc:
        return respuestas.error(str(exc), 400, codigo='VALIDACION')

    afectadas = model.update(id, data, empleado_id=empleado_actual_id())
    if not afectadas:
        return respuestas.error('Gasto no encontrado', 404, codigo='NO_ENCONTRADO')

    return respuestas.recurso(model.get_by_id(id), mensaje='Gasto actualizado')


@requiere_permiso('caja.crear')
def delete_gasto(id):
    afectadas = model.delete(id)
    if not afectadas:
        return respuestas.error('Gasto no encontrado', 404, codigo='NO_ENCONTRADO')
    return respuestas.sin_contenido('Gasto eliminado')
