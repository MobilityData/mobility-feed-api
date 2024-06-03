import requests

from database.database import Database
from sqlacodegen_models import Gtfsdataset
from unidecode import unidecode
import pandas as pd

EXPECTED_VALIDATION_VERSION = "5.0.1"
FLEX_FILES = [
    "booking_rules.txt",
    "locations.geojson",
    "location_groups.txt"
]

legacy_id_format = "{country_code}-{subdivision_name}-{provider}-{data_type}-{mdb_source_id}"
db = Database(echo_sql=False)
session = db.session
latest_datasets: [Gtfsdataset] = session.query(Gtfsdataset).filter(Gtfsdataset.latest == True).all()


def normalize(string):
    string = string.split(",")[0]
    string = string.strip()
    string = string.replace(" - ", " ")
    string = "-".join(
        ("".join(s for s in string.lower() if s.isalnum() or s in [" ", "-"])).split()
    )
    string = unidecode(string, "utf-8")
    return unidecode(string)


data_quality_results = []
data_depth_results = []
files_in_report = []
flex_files_in_report = []

i = 0
for dataset in latest_datasets:
    i += 1
    print(f"Processing {dataset.feed.stable_id} ({i}/{len(latest_datasets)})")
    feed = dataset.feed
    country_code = feed.locations[0].country_code
    subdivision_name = feed.locations[0].subdivision_name
    subdivision_name = subdivision_name if subdivision_name is not None else 'unknown'
    provider = feed.provider
    data_type = 'gtfs'
    mdb_source_id = '0'
    for external_id in feed.externalids:
        if external_id.source == 'mdb':
            mdb_source_id = external_id.associated_id
            break
    legacy_id = legacy_id_format.format(
        country_code=normalize(country_code),
        subdivision_name=normalize(subdivision_name),
        provider=normalize(provider),
        data_type=data_type,
        mdb_source_id=mdb_source_id,
    )
    legacy_id = legacy_id.replace('--', '-')

    for validation_report in dataset.validation_reports:
        if validation_report.validator_version == EXPECTED_VALIDATION_VERSION:
            url = validation_report.json_report
            if url is not None:
                # Read json report from url
                try:
                    json_report = requests.get(url).json()
                    included_files = json_report['summary']['files']
                    included_files_str = ', '.join(included_files)
                    files_in_report.append({
                        'Feed Stable ID': feed.stable_id,
                        'Catalog ID': legacy_id,
                        'Files': included_files_str,
                    })
                    contains_flex_files = any(flex_file in included_files for flex_file in FLEX_FILES)
                    if contains_flex_files:
                        included_flex_files = [flex_file for flex_file in FLEX_FILES if flex_file in included_files]
                        flex_files_in_report.append({
                            'Feed Stable ID': feed.stable_id,
                            'Catalog ID': legacy_id,
                            'Files': included_flex_files,
                        })
                        print(f"Flex files found in {feed.stable_id} ({legacy_id}) - {included_flex_files}")
                except Exception as e:
                    print(f"Failed to read json report from {url}")
                    continue
            for notice in validation_report.notices:
                data_quality_results.append(
                    {
                        'Feed Stable ID': feed.stable_id,
                        'Catalog ID': legacy_id,
                        'Code': notice.notice_code,
                        'Counter': notice.total_notices,
                        'Severity': notice.severity,
                    }
                )
            for feature in validation_report.features:
                data_depth_results.append(
                    {
                        'Feed Stable ID': feed.stable_id,
                        'Catalog ID': legacy_id,
                        'Feature': feature.name,
                    }
                )
db.close_session()
pd.DataFrame(data_depth_results).to_csv('dataDepth.csv', index=False)
pd.DataFrame(data_quality_results).to_csv('dataQuality.csv', index=False)
pd.DataFrame(files_in_report).to_csv('filesReport.csv', index=False)
pd.DataFrame(flex_files_in_report).to_csv('flexFilesReport.csv', index=False)
(pd.DataFrame(data_depth_results)
 .groupby('Feature')
 .size()
 .reset_index(name='Count')
 .to_csv('dataDepthSummary.csv', index=False))
if __name__ == '__main__':
    print("Completed.")
