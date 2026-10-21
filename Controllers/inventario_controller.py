from flask import request

from Models.inventario_model import (
    TIPOS_MOVIMIENTO, InventarioModel, StockInsuficiente,
)
from utils import respuestas
from utils.decorators import empleado_actual_id, requiere_permiso
from utils.validacion import a_decimal, a_entero, descartados, filtrar

model = InventarioModel()

CAMPOS_PRODUCTO = ('nombre', 'categoria', 'tipo_consumo_id', 'precio_unitario',
                   'stock_minimo', 'stock_inicial')

CAMPOS_MOVIMIENTO = ('producto_id', 'tipo_movimiento', 'cantidad',
                     'referencia', 'observacion')


@requiere_permiso('inventario.ver')
def get_all_productos():
    return respuestas.lista(model.get_all())


@requiere_permiso('inventario.ver')
def get_producto(id):
    producto = model.get_by_id(id)
    if not producto:
        return respuestas.error('Producto no encontrado', 404, codigo='NO_ENCONTRADO')
    return respuestas.recurso(producto)


@requiere_permiso('inventario.ver')
def get_productos_por_reponer():
    return respuestas.lista(model.get_por_reponer())


@requiere_permiso('inventario.mover')
def create_producto():
    """
    F44 — Crea el producto y su stock inicial en una sola transacción.
    Antes eran dos llamadas y el stock podía quedarse sin registrar.
    """
    data, faltantes = filtrar(request.json, CAMPOS_PRODUCTO,
                              obligatorios=('nombre',))
    if faltantes:
        return respuestas.error('nombre es requerido', 400,
                                codigo='CAMPOS_REQUERIDOS')

    try:
        a_decimal(data.get('precio_unitario', 0), campo='precio_unitario', minimo=0)
        a_entero(data.get('stock_minimo', 5), campo='stock_minimo', minimo=0)
        a_entero(data.get('stock_inicial', 0), campo='stock_inicial', minimo=0)
    except ValueError as exc:
        return respuestas.error(str(exc), 400, codigo='VALIDACION')

    nuevo_id = model.create(data, empleado_id=empleado_actual_id())
    return respuestas.creado(model.get_by_id(nuevo_id),
                             mensaje='Producto creado',
                             ignorados=descartados(request.json, CAMPOS_PRODUCTO))


@requiere_permiso('inventario.mover')
def update_producto(id):
    data, _ = filtrar(request.json, CAMPOS_PRODUCTO + ('activo',))
    data.pop('stock_inicial', None)   # sólo aplica al crear

    if not data:
        return respuestas.error('No se envió ningún campo editable', 400,
                                codigo='SIN_CAMBIOS')

    afectadas = model.update(id, data)
    if not afectadas:
        return respuestas.error('Producto no encontrado', 404, codigo='NO_ENCONTRADO')
    return respuestas.recurso(model.get_by_id(id), mensaje='Producto actualizado')


@requiere_permiso('inventario.mover')
def delete_producto(id):
    afectadas = model.delete(id)
    if not afectadas:
        return respuestas.error('Producto no encontrado', 404, codigo='NO_ENCONTRADO')
    return respuestas.sin_contenido('Producto desactivado')


@requiere_permiso('inventario.ver')
def get_movimientos_producto(producto_id):
    return respuestas.lista(model.get_movimientos(producto_id))


@requiere_permiso('inventario.mover')
def registrar_movimiento():
    data, faltantes = filtrar(
        request.json, CAMPOS_MOVIMIENTO,
        obligatorios=('producto_id', 'tipo_movimiento', 'cantidad'),
    )
    if faltantes:
        return respuestas.error(
            f"Faltan campos requeridos: {', '.join(faltantes)}", 400,
            codigo='CAMPOS_REQUERIDOS', campos=faltantes)

    if data['tipo_movimiento'] not in TIPOS_MOVIMIENTO:
        return respuestas.error(
            f'tipo_movimiento debe ser uno de: {list(TIPOS_MOVIMIENTO)}', 400,
            codigo='VALIDACION')

    try:
        a_entero(data.get('cantidad'), campo='cantidad', minimo=1)
    except ValueError as exc:
        return respuestas.error(str(exc), 400, codigo='VALIDACION')

    try:
        nuevo_id = model.registrar_movimiento(data,
                                              empleado_id=empleado_actual_id())
    except StockInsuficiente as exc:
        return respuestas.error(
            f'Stock insuficiente: hay {exc.disponible} y se piden {exc.pedido}',
            409, codigo='STOCK_INSUFICIENTE',
            stock_disponible=exc.disponible, cantidad_pedida=exc.pedido)
    except ValueError as exc:
        errores = {
            'producto_no_encontrado': ('Producto no encontrado', 404,
                                       'NO_ENCONTRADO'),
            'cantidad_invalida': ('La cantidad debe ser mayor que 0', 400,
                                  'VALIDACION'),
            'tipo_movimiento_invalido': ('tipo_movimiento inválido', 400,
                                         'VALIDACION'),
        }
        mensaje, status, codigo = errores.get(
            str(exc), ('Error de validación', 400, 'VALIDACION'))
        return respuestas.error(mensaje, status, codigo=codigo)

    return respuestas.creado({'id': nuevo_id,
                              'producto': model.get_by_id(data['producto_id'])},
                             mensaje='Movimiento registrado')


@requiere_permiso('inventario.mover')
def consumo_habitacion():
    """
    §7.1 — POST /inventario/consumo-habitacion

    Descuenta el stock y crea el consumo en UNA transacción. Antes eran dos
    llamadas sueltas: si la segunda fallaba, el stock ya había bajado y nadie
    cobraba el producto (F42).

    El precio y el tipo de consumo salen del PRODUCTO, no del cliente: eso
    cierra el precio libre (F15) y la categorización a ojo (F43).
    """
    data, faltantes = filtrar(
        request.json, ('producto_id', 'reserva_habitacion_id', 'cantidad'),
        obligatorios=('producto_id', 'reserva_habitacion_id', 'cantidad'),
    )
    if faltantes:
        return respuestas.error(
            f"Faltan campos requeridos: {', '.join(faltantes)}", 400,
            codigo='CAMPOS_REQUERIDOS', campos=faltantes)

    try:
        cantidad = a_entero(data['cantidad'], campo='cantidad', minimo=1)
    except ValueError as exc:
        return respuestas.error(str(exc), 400, codigo='VALIDACION')

    try:
        movimiento_id, consumo_id, producto = model.consumo_habitacion(
            data['producto_id'], data['reserva_habitacion_id'], cantidad,
            empleado_id=empleado_actual_id(),
        )
    except StockInsuficiente as exc:
        return respuestas.error(
            f'Stock insuficiente: hay {exc.disponible} y se piden {exc.pedido}',
            409, codigo='STOCK_INSUFICIENTE',
            stock_disponible=exc.disponible, cantidad_pedida=exc.pedido)
    except ValueError as exc:
        errores = {
            'producto_no_encontrado': ('Producto no encontrado', 404,
                                       'NO_ENCONTRADO'),
            'producto_sin_tipo_consumo': (
                'El producto no tiene un tipo de consumo asignado. '
                'Asígnaselo antes de cobrarlo a una habitación.',
                409, 'PRODUCTO_SIN_TIPO_CONSUMO'),
            'reserva_habitacion_no_encontrada': (
                'La habitación de la reserva no existe', 404, 'NO_ENCONTRADO'),
            'cantidad_invalida': ('La cantidad debe ser mayor que 0', 400,
                                  'VALIDACION'),
        }
        mensaje, status, codigo = errores.get(
            str(exc), ('Error de validación', 400, 'VALIDACION'))
        return respuestas.error(mensaje, status, codigo=codigo)

    from Models.consumo_model import ConsumoModel
    return respuestas.creado(
        {
            'movimiento_id': movimiento_id,
            'consumo': ConsumoModel().get_by_id(consumo_id),
            'producto': model.get_by_id(data['producto_id']),
        },
        mensaje='Consumo de habitación registrado',
    )
