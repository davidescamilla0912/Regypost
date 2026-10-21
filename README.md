# RegyHotel Backend

API REST para la operación de RegyHotel. El backend gestiona autenticación, empleados y roles, clientes, habitaciones, reservas, acompañantes, consumos, pagos, inventario, gastos, parqueadero y caja.

## Tecnologías

- Python 3.13.13 y Flask 3.1.
- MySQL/MariaDB mediante `mysql-connector-python`.
- JWT para autenticación y permisos basados en roles.
- Flask-CORS para permitir solicitudes desde el frontend local `http://localhost:3000`.
- Gunicorn como servidor WSGI de producción.

## Requisitos

- Python 3.13 o una versión compatible con las dependencias del proyecto.
- MySQL o MariaDB disponible. La configuración local predeterminada usa `127.0.0.1:3307` y la base `hotel_db`.
- Un esquema base de RegyHotel ya creado. Este repositorio no contiene un volcado completo de la base de datos; la migración incluida modifica tablas existentes.

## Instalación local en Windows

Desde la carpeta raíz del backend, crea y activa un entorno virtual:

```powershell
py -3.13 -m venv venv
.\venv\Scripts\Activate.ps1
```

Instala las dependencias:

```powershell
pip install -r requirements.txt
```

Configura las variables de conexión y autenticación en el entorno de PowerShell antes de iniciar la API. Usa los valores de tu propia instalación:

```powershell
$env:MYSQLHOST = "127.0.0.1"
$env:MYSQLUSER = "root"
$env:MYSQLPASSWORD = ""
$env:MYSQLDATABASE = "hotel_db"
$env:MYSQLPORT = "3307"
$env:JWT_SECRET_KEY = "reemplaza-por-una-clave-aleatoria-larga"
$env:JWT_ACCESS_TOKEN_EXPIRES = "28800"
```

Arranca el servidor de desarrollo:

```powershell
python app.py
```

La API estará disponible en `http://127.0.0.1:5000`. Una solicitud `GET /` devuelve el estado básico del servicio.

No uses la clave JWT predeterminada de `Config.py` en producción. Configura una clave secreta aleatoria mediante `JWT_SECRET_KEY` y no publiques credenciales ni archivos `.env`.

## Migraciones

Con la base de datos y su esquema base ya creados, ejecuta las migraciones versionadas:

```powershell
python migrations/run.py
```

El ejecutor procesa los archivos SQL en orden alfabético y tolera determinados errores de objetos que ya existen. Revisa el resultado y crea un respaldo de la base antes de aplicar cambios en un entorno importante.

## Contrato de respuestas

Las respuestas de recursos usan `{ "data": { ... } }`; las colecciones, `{ "data": [...], "total": N }`. Los errores usan `{ "error": "...", "codigo": "..." }`. Fechas y horas se serializan en formato ISO-8601.

Las rutas están agrupadas en los módulos de `Routes/`. El login se realiza en `POST /auth/login`; el resto de rutas protegidas requiere `Authorization: Bearer <token>`. Los permisos se incluyen en el JWT y se verifican en los controladores.

## Pruebas

El proyecto incluye scripts de aceptación e integración en `tests/`:

- `tests/test_aceptacion.py`
- `tests/test_concurrencia.py`

Estas pruebas dependen de MySQL/MariaDB, tablas y datos semilla. Pueden crear, modificar y eliminar registros de prueba en la base configurada; ejecútalas únicamente contra una base de desarrollo preparada y respaldada. No las ejecutes contra producción.

## Ejecución en producción

El `Procfile` inicia Gunicorn. El proceso requiere una variable `PORT` proporcionada por la plataforma y las variables de configuración de MySQL y JWT descritas arriba:

```text
gunicorn app:app --bind 0.0.0.0:$PORT
```

Desactiva el modo de depuración en producción y configura el almacenamiento compartido para los límites de solicitudes de Flask-Limiter; el almacenamiento en memoria predeterminado es apropiado solo para desarrollo de un solo proceso.

## Estructura

```text
Controllers/  Validación de entrada, permisos y respuestas HTTP
Models/       Consultas SQL, reglas de negocio y transacciones
Routes/       Registro de rutas Flask
migrations/   Cambios versionados del esquema existente
tests/        Pruebas de aceptación y concurrencia
utils/        Respuestas, validación, fechas y autorización
app.py        Creación y configuración de la aplicación Flask
Config.py     Configuración de MySQL y JWT desde variables de entorno
database.py   Conexión a MySQL/MariaDB
```
