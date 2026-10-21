from flask import request

from Models.empleado_model import EmpleadoModel
from Models.rol_model import RolModel
from utils import respuestas
from utils.decorators import (
    empleado_actual_id, es_admin, requiere_permiso,
)
from utils.validacion import descartados, filtrar, fusionar

model = EmpleadoModel()
rol_model = RolModel()

CAMPOS_CREAR = ('nombre', 'apellido', 'usuario', 'contrasena', 'telefono',
                'email')
CAMPOS_EDITAR = ('nombre', 'apellido', 'usuario', 'telefono', 'email', 'activo')

# §5.1 punto 4 — Roles que sólo un admin puede otorgar o quitar. Sin esto,
# cualquiera con `roles.gestionar` podía asignarse 'admin' a sí mismo (F37).
ROLES_PRIVILEGIADOS = {'admin', 'gerente'}


@requiere_permiso('empleados.gestionar')
def get_all_empleados():
    return respuestas.lista(model.get_all())


@requiere_permiso('empleados.gestionar')
def get_empleado(id):
    empleado = model.get_by_id(id)
    if not empleado:
        return respuestas.error('Empleado no encontrado', 404,
                                codigo='NO_ENCONTRADO')
    return respuestas.recurso(empleado)


@requiere_permiso('empleados.gestionar')
def create_empleado():
    data, faltantes = filtrar(
        request.json, CAMPOS_CREAR,
        obligatorios=('nombre', 'usuario', 'contrasena'),
    )
    if faltantes:
        return respuestas.error(
            f"Faltan campos requeridos: {', '.join(faltantes)}", 400,
            codigo='CAMPOS_REQUERIDOS', campos=faltantes)

    nuevo_id = model.create(data)
    return respuestas.creado(model.get_by_id(nuevo_id),
                             mensaje='Empleado creado',
                             ignorados=descartados(request.json, CAMPOS_CREAR))


@requiere_permiso('empleados.gestionar')
def update_empleado(id):
    """
    §5.2 — `rol_id` y `contrasena` no se aceptan aquí: tienen sus propios
    endpoints. Así una edición de perfil no puede cambiar privilegios.
    """
    data, _ = filtrar(request.json, CAMPOS_EDITAR)
    if not data:
        return respuestas.error('No se envió ningún campo editable', 400,
                                codigo='SIN_CAMBIOS',
                                campos_editables=list(CAMPOS_EDITAR))

    actual = model.get_by_id(id)
    if not actual:
        return respuestas.error('Empleado no encontrado', 404,
                                codigo='NO_ENCONTRADO')

    afectadas = model.update(id, fusionar(actual, data, CAMPOS_EDITAR))
    if not afectadas:
        return respuestas.error('Empleado no encontrado', 404,
                                codigo='NO_ENCONTRADO')

    return respuestas.recurso(model.get_by_id(id), mensaje='Empleado actualizado',
                              ignorados=descartados(request.json, CAMPOS_EDITAR))


@requiere_permiso('empleados.gestionar')
def update_contrasena_empleado(id):
    data = request.json or {}
    contrasena = data.get('contrasena')
    if not contrasena:
        return respuestas.error('contrasena es requerida', 400,
                                codigo='CAMPOS_REQUERIDOS')
    if len(str(contrasena)) < 6:
        return respuestas.error('La contraseña debe tener al menos 6 caracteres',
                                400, codigo='VALIDACION')

    afectadas = model.update_contrasena(id, contrasena)
    if not afectadas:
        return respuestas.error('Empleado no encontrado', 404,
                                codigo='NO_ENCONTRADO')
    return respuestas.sin_contenido('Contraseña actualizada')


@requiere_permiso('empleados.gestionar')
def delete_empleado(id):
    if id == empleado_actual_id():
        return respuestas.error('No puedes eliminar tu propio usuario', 409,
                                codigo='AUTO_ELIMINACION')

    afectadas = model.delete(id)
    if not afectadas:
        return respuestas.error('Empleado no encontrado', 404,
                                codigo='NO_ENCONTRADO')
    return respuestas.sin_contenido('Empleado eliminado')


# ─── §5.1 punto 4 — ESCALADA DE PRIVILEGIOS ───────────────────────────────────

def _puede_otorgar(rol_id):
    """
    Comprueba que quien llama tenga permiso para otorgar ESE rol concreto.
    Antes bastaba `roles.gestionar` para asignarse cualquier rol (F37).

    Devuelve `(permitido, respuesta_de_error)`.
    """
    rol = rol_model.get_by_id(rol_id)
    if not rol:
        return False, respuestas.error('Rol no encontrado', 404,
                                       codigo='NO_ENCONTRADO')

    nombre = (rol.get('nombre') or '').lower()
    if nombre in ROLES_PRIVILEGIADOS and not es_admin():
        return False, respuestas.error(
            f'Solo un administrador puede otorgar o quitar el rol "{nombre}"',
            403, codigo='ESCALADA_PRIVILEGIOS', rol=nombre)

    return True, None


@requiere_permiso('roles.gestionar')
def asignar_rol_empleado(empleado_id):
    data = request.json or {}
    rol_id = data.get('rol_id')
    if not rol_id:
        return respuestas.error('rol_id es requerido', 400,
                                codigo='CAMPOS_REQUERIDOS')

    permitido, error = _puede_otorgar(rol_id)
    if not permitido:
        return error

    if not model.get_by_id(empleado_id):
        return respuestas.error('Empleado no encontrado', 404,
                                codigo='NO_ENCONTRADO')

    model.asignar_rol(empleado_id, rol_id)
    return respuestas.recurso(model.get_by_id(empleado_id),
                              mensaje='Rol asignado')


@requiere_permiso('roles.gestionar')
def quitar_rol_empleado(empleado_id, rol_id):
    permitido, error = _puede_otorgar(rol_id)
    if not permitido:
        return error

    # Nadie se quita a sí mismo el último rol privilegiado y se deja fuera.
    if empleado_id == empleado_actual_id():
        return respuestas.error(
            'No puedes quitarte un rol a ti mismo', 409,
            codigo='AUTO_MODIFICACION')

    model.quitar_rol(empleado_id, rol_id)
    return respuestas.recurso(model.get_by_id(empleado_id),
                              mensaje='Rol removido')
