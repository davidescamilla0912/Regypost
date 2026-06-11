import os

DB_CONFIG = {
    "host":     os.environ.get("MYSQLHOST",     "127.0.0.1"),
    "user":     os.environ.get("MYSQLUSER",     "root"),
    "password": os.environ.get("MYSQLPASSWORD", ""),
    "database": os.environ.get("MYSQLDATABASE", "hotel_db"),
    "port":     int(os.environ.get("MYSQLPORT", 3307)),
}

JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "hotel_bq84_secret_key_2026")
JWT_ACCESS_TOKEN_EXPIRES = int(os.environ.get("JWT_ACCESS_TOKEN_EXPIRES", 28800))