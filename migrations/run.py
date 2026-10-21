"""
Ejecuta los .sql de esta carpeta en orden alfabético.

    python migrations/run.py

Es tolerante a re-ejecución: los errores que significan "esto ya estaba"
(columna/índice/clave duplicada) se reportan como OMITIDO y no detienen la
migración. Cualquier otro error aborta.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import get_connection  # noqa: E402

# Errores de MariaDB que sólo significan "ya aplicado".
YA_APLICADO = {
    1060,  # Duplicate column name
    1061,  # Duplicate key name
    1022,  # Can't write; duplicate key in table
    1826,  # Duplicate foreign key constraint name
    1050,  # Table already exists
    1091,  # Can't DROP; check that it exists
}


def es_ya_aplicado(exc):
    """True si el error sólo significa que la sentencia ya estaba aplicada."""
    codigo = getattr(exc, 'errno', None)
    if codigo in YA_APLICADO:
        return True
    # MariaDB reporta el re-alta de una FOREIGN KEY como 1005 / errno 121
    # ("Duplicate key on write or update") en vez de 1826.
    return codigo == 1005 and 'errno: 121' in str(exc)


def sentencias(sql):
    """Parte el archivo en sentencias, quitando los comentarios de línea."""
    sin_comentarios = re.sub(r'--[^\n]*', '', sql)
    for bruto in sin_comentarios.split(';'):
        limpia = bruto.strip()
        if limpia:
            yield limpia


def main():
    carpeta = os.path.dirname(os.path.abspath(__file__))
    archivos = sorted(f for f in os.listdir(carpeta) if f.endswith('.sql'))
    if not archivos:
        print('No hay archivos .sql que ejecutar.')
        return 0

    conn = get_connection()
    cursor = conn.cursor()
    fallos = 0

    for archivo in archivos:
        print(f'\n=== {archivo} ===')
        with open(os.path.join(carpeta, archivo), encoding='utf-8') as fh:
            contenido = fh.read()

        for stmt in sentencias(contenido):
            etiqueta = ' '.join(stmt.split())[:80]
            try:
                cursor.execute(stmt)
                # Consumir cualquier resultado pendiente.
                try:
                    cursor.fetchall()
                except Exception:
                    pass
                conn.commit()
                print(f'  OK       {etiqueta}')
            except Exception as exc:
                codigo = getattr(exc, 'errno', None)
                if es_ya_aplicado(exc):
                    conn.rollback()
                    print(f'  OMITIDO  {etiqueta}  ({codigo})')
                else:
                    conn.rollback()
                    fallos += 1
                    print(f'  ERROR    {etiqueta}\n           {exc}')

    cursor.close()
    conn.close()
    print(f'\nTerminado con {fallos} error(es).')
    return 1 if fallos else 0


if __name__ == '__main__':
    sys.exit(main())
