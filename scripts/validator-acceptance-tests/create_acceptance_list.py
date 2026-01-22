# This script connects to a PostgreSQL database using credentials from a .env file,
# executes a SQL query from create_list.sql, and writes the results to a CSV file.
# It is intended to generate a validator acceptance list for GTFS feeds.

import os
import csv
import psycopg2
import argparse
from dotenv import load_dotenv

# Parse command-line arguments for the --env-file parameter
# This allows the user to specify which .env file to use for DB credentials
def parse_args():
    parser = argparse.ArgumentParser(description="Create validator acceptance list CSV from DB query.")
    parser.add_argument('--env-file', default='config/.env.local', help='Path to .env file (default: config/.env.local)')
    return parser.parse_args()

# Define the paths for the SQL query file and the output CSV file
SQL_FILE = os.path.join(os.path.dirname(__file__), 'create_list.sql')
CSV_FILE = os.path.join(os.path.dirname(__file__), 'validator-acceptance-list.csv')

def main():
    args = parse_args()
    # Load environment variables from the specified env file
    load_dotenv(args.env_file)

    # Read PostgreSQL connection parameters from environment variables
    DB_HOST = os.getenv('POSTGRES_HOST')
    DB_PORT = os.getenv('POSTGRES_PORT')
    DB_NAME = os.getenv('POSTGRES_DB')
    DB_USER = os.getenv('POSTGRES_USER')
    DB_PASS = os.getenv('POSTGRES_PASSWORD')

    # Print DB connection variables (except password) for debugging
    print(f"Connecting to PostgreSQL with:")
    print(f"  HOST: {DB_HOST}")
    print(f"  PORT: {DB_PORT}")
    print(f"  DB:   {DB_NAME}")
    print(f"  USER: {DB_USER}")

    # Read SQL query from file
    with open(SQL_FILE, 'r') as f:
        query = f.read()

    # Connect to PostgreSQL and execute the query
    conn = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASS
    )
    cur = conn.cursor()
    # Enforce read-only session for extra safety
    cur.execute("SET SESSION CHARACTERISTICS AS TRANSACTION READ ONLY;")
    cur.execute(query)
    rows = cur.fetchall()
    headers = [desc[0] for desc in cur.description]

    # Write results to CSV file
    with open(CSV_FILE, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(headers)
        writer.writerows(rows)

    # Clean up DB connection
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
