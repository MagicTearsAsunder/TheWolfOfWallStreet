import psycopg2
import sys

# Configure connection to your database. Assume you are using default port 5432.
try:
    conn = psycopg2.connect(dbname="Your_Database_Name", user="Your_Username", password="Your_Password", host="localhost")
except psycopg2.Error as connection_error:
    print(connection_error)
    sys.exit("Database connection failed")

cur = conn.cursor()

# Create table "users"
try:
    cur.execute("CREATE TABLE users "
                "(username VARCHAR(50) NOT NULL PRIMARY KEY, "
                "hashed_password VARCHAR(150) NOT NULL, "
                "current_cash NUMERIC(9,2) NOT NULL, "
                "user_transactions UUID, "
                "UNIQUE(user_transactions))")
except psycopg2.Error as psycopg_error:
    print(psycopg_error)
    conn.rollback()
    cur.close()
    conn.close()
    sys.exit("Table users creation Error.")

conn.commit()
cur.close()
cur = conn.cursor()

# Create table "transactions"
try:
    cur.execute("CREATE TABLE transactions "
            "(username VARCHAR(50) NOT NULL, "
            "symbol VARCHAR(10) NOT NULL, "
            "shares INTEGER NOT NULL,price NUMERIC(7,2) NOT NULL, "
            "time TIMESTAMP NOT NULL, "
            "trans_uid UUID REFERENCES users(user_transactions))")
except psycopg2.Error as psycopg_error2:
    print(psycopg_error2)
    conn.rollback()
    cur.close()
    conn.close()
    sys.exit("Table transactions creation Error.")
else:
    conn.commit()
    cur.close()
    conn.close()
    print("Users and Transactions table have been successfully created.")
