import pandas as pd
import os
import yaml

with open("./config.yaml", "r") as stream:
    try:
        CONFIG = yaml.safe_load(stream)
    except yaml.YAMLError as exc:
        logging.error('Exception occurred while loading config.yaml', exc)

# Define file paths
raw_data_path = CONFIG['PATH']["RAW_DATA"]
processed_data_path = CONFIG['PATH']["PROCESSED_DATA"]

try:
    # Load raw CSV data
    raw_data = pd.read_csv(raw_data_path)
except FileNotFoundError:
    print(f"Error: The file at {raw_data_path} was not found.")
    exit(1)
except pd.errors.EmptyDataError:
    print("Error: The CSV file is empty.")
    exit(1)
except Exception as e:
    print(f"An error occurred while reading the CSV file: {e}")
    exit(1)

# Preview first few rows (optional)
print(raw_data.head())

# Function to format movie information into a single string
def format_movie_data(row):
    try:
        return (
            f"Title: {row.get('Title', '')}\n"
            f"Certificate: {row.get('Certificate', '')}\n"
            f"Duration: {row.get('Duration', '')}\n"
            f"Genre: {row.get('Genre', '')}\n"
            f"Rate: {row.get('Rate', '')}\n"
            f"Metascore: {row.get('Metascore', '')}\n"
            f"Description: {row.get('Description', '')}\n"
            f"Cast: {row.get('Cast', '')}\n"
            f"Info: {row.get('Info', '')}\n"
        )
    except Exception as e:
        print(f"Error formatting row: {e}")
        return ""

# Apply formatting function to each row to create 'movie_data' column
raw_data['movie_data'] = raw_data.apply(format_movie_data, axis=1)

# Extract only the 'movie_data' column into a new DataFrame
processed_data = raw_data[["movie_data"]].copy()

# Ensure the output directory exists
os.makedirs(os.path.dirname(processed_data_path), exist_ok=True)

try:
    # Save the processed data to CSV
    processed_data.to_csv(processed_data_path, index=False)
    print(f"Processed data saved to {processed_data_path}")
except Exception as e:
    print(f"An error occurred while writing to CSV: {e}")
