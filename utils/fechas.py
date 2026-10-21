"""
§2.4 — Fechas, horas y zona horaria.

DECISIÓN TOMADA (variante de la Opción B del documento, sin cambios en el
frontend):

  * La base de datos guarda las marcas de tiempo en **hora local de Colombia**.
    No es una preferencia: `pagos.fecha_pago` y `movimientos_inventario.fecha`
    ya tienen filas escritas con `CURRENT_TIMESTAMP` y el servidor MySQL corre
    en `SYSTEM` = America/Bogota. Guardar UTC de aquí en adelante habría
    partido el histórico en dos y descuadrado los cierres de caja anteriores.

  * La API **acepta ambos formatos** en la entrada: el ISO-8601 en UTC que el
    frontend ya envía (`"2026-09-10T01:30:00.000Z"`) y la hora local sin zona
    (`"2026-09-09 20:30:00"`). `a_datetime_local()` normaliza cualquiera de los
    dos a hora de Bogotá antes de escribir.

  * La API **devuelve** las marcas de tiempo con el desfase explícito
    (`"2026-09-09T20:30:00-05:00"`), así que ya no hay ambigüedad posible.

  * Agrupar por día (cuadres, reportes) usa el día calendario de Bogotá.

Con esto, un pago hecho a las 20:30 hora Colombia cae en el cuadre de HOY y no
en el de mañana (F16).

Las fechas sin hora (`fecha_entrada`, `fecha_salida`, `consumos.fecha`) son
fechas de calendario puras y no llevan zona horaria nunca.
"""
from datetime import date, datetime, time, timedelta, timezone

# Colombia es UTC-5 todo el año: no aplica horario de verano desde 1993.
OFFSET_COLOMBIA = timedelta(hours=-5)

try:  # Preferimos la zona real si el sistema tiene la base de datos tz.
    from zoneinfo import ZoneInfo

    TZ_LOCAL = ZoneInfo('America/Bogota')
except Exception:  # Windows sin el paquete `tzdata` cae aquí.
    TZ_LOCAL = timezone(OFFSET_COLOMBIA, 'America/Bogota')


def ahora_local():
    """`datetime` consciente de zona, en hora de Bogotá."""
    return datetime.now(TZ_LOCAL)


def hoy_local():
    """Fecha de calendario de hoy en Bogotá (no la del servidor en UTC)."""
    return ahora_local().date()


def a_datetime_local(valor):
    """
    Normaliza a hora local de Bogotá cualquier marca de tiempo que llegue.

    Acepta:
      - `"2026-09-10T01:30:00.000Z"`  (ISO-8601 en UTC, lo que envía el front)
      - `"2026-09-09T20:30:00-05:00"` (ISO-8601 con desfase explícito)
      - `"2026-09-09 20:30:00"`       (hora local sin zona)
      - un `datetime` o un `date`

    Devuelve un `datetime` **naive** en hora local, listo para escribir en un
    DATETIME/TIMESTAMP de MySQL. Devuelve None si el valor es vacío.
    Lanza ValueError si el texto no es una marca de tiempo reconocible.
    """
    if valor is None or valor == '':
        return None

    if isinstance(valor, datetime):
        momento = valor
    elif isinstance(valor, date):
        return datetime.combine(valor, time.min)
    else:
        texto = str(valor).strip()
        # `fromisoformat` de Python 3.11+ entiende la 'Z', pero normalizamos
        # igual para tolerar versiones anteriores y el espacio como separador.
        if texto.endswith(('Z', 'z')):
            texto = texto[:-1] + '+00:00'
        try:
            momento = datetime.fromisoformat(texto)
        except ValueError:
            raise ValueError(f'Marca de tiempo inválida: {valor!r}')

    if momento.tzinfo is None:
        # Sin zona = ya viene en hora local; se guarda tal cual.
        return momento
    return momento.astimezone(TZ_LOCAL).replace(tzinfo=None)


def marcar_local(momento):
    """
    Etiqueta como hora de Bogotá un `datetime` naive leído de la base de datos,
    para que al serializarlo salga con el desfase explícito (`-05:00`).
    """
    if not isinstance(momento, datetime):
        return momento
    if momento.tzinfo is not None:
        return momento
    return momento.replace(tzinfo=TZ_LOCAL)


def a_fecha(valor):
    """
    Normaliza una fecha de calendario (`"2026-09-09"`) a `date`.
    Devuelve None si viene vacía; lanza ValueError si no es una fecha válida.
    """
    if valor is None or valor == '':
        return None
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    try:
        return date.fromisoformat(str(valor).strip()[:10])
    except ValueError:
        raise ValueError(f'Fecha inválida: {valor!r}')


def rango_del_dia(dia):
    """
    Devuelve `(inicio, fin)` naive en hora local que cubren el día calendario
    de Bogotá, para filtrar columnas TIMESTAMP con `>= inicio AND < fin`.
    """
    dia = a_fecha(dia)
    inicio = datetime.combine(dia, time.min)
    return inicio, inicio + timedelta(days=1)


def noches_entre(entrada, salida):
    """Número de noches de una estadía. Siempre >= 0."""
    entrada = a_fecha(entrada)
    salida = a_fecha(salida)
    if not entrada or not salida:
        return 0
    return max((salida - entrada).days, 0)
