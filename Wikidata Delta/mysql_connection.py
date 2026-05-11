
import mysql.connector


def create_mysql_connection(host, user, password, database, db_port):
    try:
        cnx = mysql.connector.connect(
            host=host,
            user=user,
            password=password,
            database=database,
            port=db_port
        )
        cursor = cnx.cursor(buffered=True)
        return cnx, cursor
    except mysql.connector.Error as err:
        return None, None