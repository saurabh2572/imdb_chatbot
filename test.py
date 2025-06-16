import sqlite3
def read_sql_query(sql, db):
    """
    Executes a SQL SELECT query on the specified SQLite database and returns the results.

    Parameters:
    - sql (str): The SQL query to execute.
    - db (str): The path to the SQLite database file.

    Returns:
    - list: A list of rows returned by the SQL query.
    """
    try:
        # Connect to the SQLite database
        conn = sqlite3.connect(db)
        cur = conn.cursor()

        # Execute the provided SQL query
        cur.execute(sql)

        # Fetch all rows from the result
        rows = cur.fetchall()

        # No changes made, so no commit needed for SELECT queries (safe to keep for other query types)
        conn.commit()

        print("Rows retrieved from SQL successfully")

        # Return the retrieved rows
        return rows

    except Exception as e:
        print(f"Error occurred while reading from SQL: {e}")
        return None

    finally:
        # Ensure the connection is closed even if an error occurs
        if 'conn' in locals():
            conn.close()

read_sql_query(sql="SELECT Rate, explode(Cast) as Cast FROM imdb_dataset  ORDER BY Rate DESC LIMIT 5", db="imdb_dataset.db")