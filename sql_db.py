import sqlite3
import pandas as pd
import yaml
import logging

with open("./config.yaml", "r") as stream:
    try:
        CONFIG = yaml.safe_load(stream)
    except yaml.YAMLError as exc:
        logging.error('Exception occurred while loading config.yaml', exc)

def load_csv_to_sqlite(db_path, csv_path):
    """
    Creates an IMDb dataset table in SQLite and loads processed CSV data into it.

    Parameters:
    - db_path (str): Path to the SQLite database file.
    - csv_path (str): Path to the processed CSV file.

    Returns:
    - None
    """
    try:
        # Establish SQLite connection
        with sqlite3.connect(db_path) as connection:
            cursor = connection.cursor()

            # Define SQL table schema
            create_table_sql = """
            CREATE TABLE IF NOT EXISTS imdb_dataset (
                Title VARCHAR(255),
                Certificate VARCHAR(50),
                Duration INT,
                Genre VARCHAR(100),
                Rate FLOAT,
                Metascore FLOAT,
                Description TEXT,
                Cast TEXT,
                Info TEXT,
                Votes BIGINT,
                Gross DOUBLE
            );
            """
            cursor.execute(create_table_sql)
            print("Table imdb_dataset created successfully (or already exists).")

            # Load and preprocess the CSV data
            df = pd.read_csv(csv_path)
            df = df.where(pd.notnull(df), None)  # Replace NaN with None
            if 'Unnamed: 0' in df.columns:
                df.drop('Unnamed: 0', axis=1, inplace=True)

            # Insert rows into the table
            for _, row in df.iterrows():
                cursor.execute("""
                INSERT INTO imdb_dataset (
                    Title, Certificate, Duration, Genre, Rate, Metascore,
                    Description, Cast, Info, Votes, Gross
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, tuple(row))

            connection.commit()
            print("Data inserted successfully into imdb_dataset.")

    except Exception as e:
        print(f"[Error] Failed to load data into SQLite DB: {e}")

# Example usage
load_csv_to_sqlite("imdb_dataset.db", CONFIG['PATH']["SQL_PROCESSED_DATA"])