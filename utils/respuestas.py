"""
§2.1 y §2.2 — Forma única de las respuestas de la API.

Antes cada endpoint devolvía lo que le parecía: unos un array plano, otros
`{"data": [...]}`, y los errores llegaban bajo cuatro claves distintas
(`message`, `error`, `detail`, `mensaje`). El frontend tenía que adivinar.

A partir de aquí:

    Colección  -> {"data": [ ... ], "total": N}
    Recurso    -> {"data": { ... }}
    Error      -> {"error": "texto legible", "codigo": "CODIGO_ESTABLE"}
"""
from datetime import date, datetime, time, timedelta
from decimal import Decimal
import json

from flask import Response


def serializar(obj):
    """Convierte a JSON los tipos que devuelve MySQL y `json` no sabe manejar."""
    if isinstance(obj, timedelta):
        total = int(obj.total_seconds())
        return f'{total // 3600:02d}:{(total % 3600) // 60:02d}'
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, date):
        return obj.isoformat()
    if isinstance(obj, time):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, bytes):
        return obj.decode('utf-8', 'replace')
    raise TypeError(f'No se puede serializar {type(obj).__name__}')


def _json(payload, status):
    return Response(
        json.dumps(payload, default=serializar, ensure_ascii=False),
        status=status,
        mimetype='application/json',
    )


def lista(filas, total=None, **extra):
    """Respuesta de colección: {"data": [...], "total": N}."""
    filas = list(filas or [])
    cuerpo = {'data': filas, 'total': total if total is not None else len(filas)}
    cuerpo.update(extra)
    return _json(cuerpo, 200)


def recurso(fila, status=200, **extra):
    """Respuesta de recurso individual: {"data": {...}}."""
    cuerpo = {'data': fila}
    cuerpo.update(extra)
    return _json(cuerpo, status)


def creado(fila, **extra):
    """201 Created con el recurso ya creado dentro de `data`."""
    return recurso(fila, status=201, **extra)


def error(mensaje, status=400, codigo=None, **extra):
    """
    Respuesta de error. `error` siempre trae el texto legible; `codigo` es un
    identificador estable para que el frontend pueda reaccionar distinto según
    el motivo sin tener que leer el texto.
    """
    cuerpo = {'error': mensaje}
    if codigo:
        cuerpo['codigo'] = codigo
    cuerpo.update(extra)
    return _json(cuerpo, status)


def sin_contenido(mensaje='Operación realizada'):
    """Para DELETE y operaciones que no devuelven un recurso."""
    return _json({'data': None, 'mensaje': mensaje}, 200)
