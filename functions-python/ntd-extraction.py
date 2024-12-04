import pandas as pd
import requests
import os
import tempfile
from contextlib import contextmanager
from helpers.database import start_db_session
from sqlacodegen_models import Gtfsfeed
import zipfile
import shutil


@contextmanager
def temp_directory():
    """
    Context manager to create and clean up a temporary directory.
    """
    temp_dir = tempfile.mkdtemp()
    try:
        yield temp_dir
    finally:
        shutil.rmtree(temp_dir)


def validate_zip_file(url):
    """
    Validates if the file at the given URL is a valid zip file.
    :param url: URL of the zip file.
    :return: True if valid, False otherwise.
    """
    print(f'Validating {url}')
    try:
        response = requests.get(url, timeout=10)
        print(f'Status code: {response.status_code}')
        if response.status_code != 200:
            return False
    except Exception as e:
        print(f'Error: {e} - Failed to fetch the zip file')
        return False

    # Create a temporary directory to safely extract files
    with temp_directory() as temp_dir:
        temp_zip_path = os.path.join(temp_dir, 'temp.zip')
        try:
            # Save the zip file to the temporary directory
            with open(temp_zip_path, 'wb') as f:
                f.write(response.content)

            # Validate the zip file by attempting to extract it
            with zipfile.ZipFile(temp_zip_path) as z:
                z.extractall(temp_dir)
            print('Zip file is valid')
            return True
        except Exception as e:
            print(f'Error: {e} - Zip file is invalid')
            return False


# Fetch the Excel file with GTFS Weblinks
access_url = 'https://www.transit.dot.gov/sites/fta.dot.gov/files/2024-11/2023%20GTFS%20Weblinks.xlsx'
response = requests.get(access_url)
response.raise_for_status()

# Save and load the Excel file
with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as temp_excel:
    temp_excel.write(response.content)
    temp_excel_path = temp_excel.name

df = pd.read_excel(temp_excel_path)
os.remove(temp_excel_path)  # Clean up temporary Excel file

# Process the DataFrame
columns_to_keep = ['Weblink', 'Agency Name', 'NTD ID']
df = df[columns_to_keep]
df = df.drop_duplicates(subset=['Weblink'], keep='first')
df = df.dropna(subset=['Weblink'])

# Fetch existing URLs from the database
dev_database_url = '<secret url>'
dev_session = start_db_session(dev_database_url, echo=False)
producer_urls = dev_session.query(Gtfsfeed.producer_url).all()
producer_urls = [url[0] for url in producer_urls]
df = df[~df['Weblink'].isin(producer_urls)]

# Validate the URLs for zipped files
df['Status'] = df['Weblink'].apply(validate_zip_file)

# Filter valid URLs
df = df[df['Status']]
df.drop(columns=['Status'], inplace=True)  # Optional: remove Status column

# Save valid URLs to a CSV file
output_csv_path = 'valid_gtfs_links.csv'
df.to_csv(output_csv_path, index=False)
print(f"Valid GTFS links saved to {output_csv_path}")
print(df)
