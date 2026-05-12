import os

DB_CONFIG = {
    "host": os.environ.get("MYSQLHOST"),
    "user": os.environ.get("MYSQLUSER"),
    "password": os.environ.get("MYSQLPASSWORD"),
    "database": os.environ.get("MYSQLDATABASE"),
    "port": int(os.environ.get("MYSQLPORT", 3306))
}

JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "hotel_bq84_secret_key_2026")
JWT_ACCESS_TOKEN_EXPIRES = 28800