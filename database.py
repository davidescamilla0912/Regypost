# database.py
import mysql.connector
from Config import DB_CONFIG

def get_connection():
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        return conn
    except mysql.connector.Error as e:
        print(f"Error al conectar a la BASE DE DATOS: {e}")
        raise