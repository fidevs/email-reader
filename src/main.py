import psycopg2

try:
    connection = psycopg2.connect(
        host = 'localhost',
        user = 'postgres',
        password = 'p057gr35',
        database = 'postgres'
    )
    print("conexión exitosa")
except Exception as ex:
    print(ex)

