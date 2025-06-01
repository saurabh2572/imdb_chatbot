import pandas as pd
import yaml
import os
import re
import logging

with open("./config.yaml", "r") as stream:
    try:
        CONFIG = yaml.safe_load(stream)
    except yaml.YAMLError as exc:
        logging.error('Exception occurred while loading config.yaml', exc)

# Define file paths
raw_data_path = CONFIG['PATH']["RAW_DATA"]
processed_data_path = CONFIG['PATH']["SQL_PROCESSED_DATA"]

try:
    # Step 1: Load raw CSV data
    raw_data = pd.read_csv(raw_data_path)

    # Step 2: Clean Duration column (e.g., "120 min" → 120)
    if 'Duration' in raw_data.columns:
        raw_data['Duration'] = raw_data['Duration'].str.replace(' min', '', regex=False).astype(int)

    # Step 3: Extract Votes and Gross values using regex
    raw_data[['Votes', 'Gross']] = raw_data['Info'].str.extract(
        r'Votes:\s([\d,]+)\s\|\sGross:\s\$(\d+\.\d+)', expand=True
    )

    # Step 4: Clean and convert 'Votes'
    raw_data['Votes'] = (
        raw_data['Votes']
        .str.replace(',', '', regex=False)
        .astype(float)  # preserve NaN
        .astype('Int64')  # nullable integer
    )

    # Step 5: Convert 'Gross' to float
    raw_data['Gross'] = raw_data['Gross'].astype(float)

    # Step 6: Save cleaned dataset
    processed_data = raw_data.copy()
    processed_data.to_csv(processed_data_path, index=False)
    print(f"Data processed and saved to {processed_data_path}.")

except FileNotFoundError:
    print(f"[Error] The file at {raw_data_path} was not found.")
    exit(1)

except pd.errors.ParserError as pe:
    print(f"[Error] Failed to parse the CSV file: {pe}")
    exit(1)

except Exception as e:
    print(f"[Error] An unexpected error occurred during processing: {e}")
    exit(1)



