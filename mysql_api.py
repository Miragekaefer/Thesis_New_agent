# mysql_api.py

import mysql.connector
from mysql.connector import Error
from dotenv import load_dotenv
import os

load_dotenv()


def get_mysql_connection():
    """
    Create reusable MySQL connection.
    """

    return mysql.connector.connect(
        host=os.getenv("MYSQL_HOST"),
        port=os.getenv("MYSQL_PORT"),
        database=os.getenv("MYSQL_DATABASE"),
        user=os.getenv("MYSQL_USER"),
        password=os.getenv("MYSQL_PASSWORD")
    )


def execute_select_query(query, params=None):
    """
    SAFE READ-ONLY QUERY EXECUTION
    """

    connection = None

    try:
        connection = get_mysql_connection()

        cursor = connection.cursor(dictionary=True)

        cursor.execute(query, params or ())

        results = cursor.fetchall()

        return {
            "success": True,
            "rows": results,
            "count": len(results)
        }

    except Error as e:
        return {
            "success": False,
            "error": str(e)
        }

    finally:
        if connection and connection.is_connected():
            connection.close()


def test_connection():
    """
    Health check
    """

    try:
        connection = get_mysql_connection()

        if connection.is_connected():
            return {
                "success": True,
                "message": "MySQL connection successful"
            }

    except Error as e:
        return {
            "success": False,
            "error": str(e)
        }

    finally:
        if connection and connection.is_connected():
            connection.close()