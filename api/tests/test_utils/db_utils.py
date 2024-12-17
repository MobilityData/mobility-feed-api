import logging
from typing import Final

import pandas as pd

from geoalchemy2 import WKBElement
from geoalchemy2.shape import to_shape
from sqlalchemy import Inspector, delete
import json

from database_gen.sqlacodegen_models import Base


class CustomEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, WKBElement):
            # Convert the WKBElement to a shapely shape, then to a geojson format
            return to_shape(obj).wkt
            # return to_shape(obj).__geo_interface__
        elif isinstance(obj, pd.Timestamp):
            # Convert Timestamp object to string in ISO 8601 format
            return obj.isoformat()
        return super().default(obj)


def dump_raw_database(db, file_name="database_raw_dump.json"):
    # Create an Inspector and connect it to the engine
    inspector = Inspector.from_engine(db.engine)

    # Get the list of all tables in the database
    all_tables = inspector.get_table_names()

    tables_of_interest = [
        "feed",
        "gtfsrealtimefeed",
        "feature",
        "feedreference",
        "location",
        "locationfeed",
        "externalid",
        "gtfsdataset",
        "featurevalidationreport",
        "notice",
        "redirectingid",
        "validationreportgtfsdataset",
        "validationreport",
    ]
    tables = [table for table in all_tables if table in tables_of_interest]
    # Initialize an empty dictionary to hold data
    data = {}

    dfs = {}
    # Loop through each table
    for table in tables:
        # Read the table into a DataFrame
        df = pd.read_sql_table(table, db.engine)
        dfs[table] = df

    for table, df in dfs.items():
        if df.shape[0] > 0:
            # Convert the DataFrame into a JSON object and add it to the data dictionary
            records = df.to_dict(orient="records")
            data[table] = [{k: v for k, v in record.items() if v is not None} for record in records]

    # Write the data dictionary to a JSON file
    with open(file_name, "w") as f:
        json.dump(data, f, cls=CustomEncoder)


def dump_database(db, file_name):
    if file_name is None:
        return

    # Create an Inspector and connect it to the engine
    inspector = Inspector.from_engine(db.engine)

    # Get the list of all tables in the database
    all_tables = inspector.get_table_names()

    tables_of_interest = [
        "feed",
        "feature",
        "feedreference",
        "location",
        "locationfeed",
        "externalid",
        "gtfsdataset",
        "featurevalidationreport",
        "notice",
        "redirectingid",
        "validationreportgtfsdataset",
        "validationreport",
    ]
    tables = [table for table in all_tables if table in tables_of_interest]
    # Initialize an empty dictionary to hold data
    data = {}

    dfs = {}
    # Loop through each table
    for table in tables:
        # Read the table into a DataFrame
        df = pd.read_sql_table(table, db.engine)
        dfs[table] = df

    feeds = dfs["feed"]
    # Create a dictionary mapping feed_id to stable_id
    feed_id_to_stable_id = feeds.set_index("id")["stable_id"].to_dict()

    validationreportgtfsdatasets = dfs["validationreportgtfsdataset"]
    # merged_df_1 = pd.merge(dfs['validationreport'], dfs['validationreportgtfsdataset'], left_on='id',
    #                        right_on='validation_report_id')

    datasets = dfs["gtfsdataset"]
    dataset_id_to_stable_id = datasets.set_index("id")["stable_id"].to_dict()

    # Replace feed_id with stable_id in the gtfsdataset DataFrame
    datasets["feed_stable_id"] = datasets["feed_id"].replace(feed_id_to_stable_id)
    datasets["id"] = datasets["stable_id"]
    dfs["datasets"] = datasets.drop(columns=["feed_id", "stable_id"])

    validationreports = dfs["validationreport"]
    validationreports["name"] = ["vr_" + str(i + 1) for i in range(len(validationreports))]
    validationreport_id_to_name = validationreports.set_index("id")["name"].to_dict()
    validationreports["id"] = validationreports["id"].replace(validationreport_id_to_name)

    validationreports["dataset_id"] = validationreportgtfsdatasets["dataset_id"].replace(dataset_id_to_stable_id)
    validationreports["html_report"] = "someurl"
    validationreports["json_report"] = "someurl"
    dfs["validation_reports"] = validationreports.drop(columns=["name"])
    del dfs["validationreport"]

    features = dfs["feature"]

    # Extract the 'name' values into a list
    name_list = features["name"].values

    # Convert the list into a DataFrame
    dfs["features"] = pd.DataFrame(name_list)

    del dfs["feature"]

    featurevalidationreports = dfs.get("featurevalidationreport")

    featurevalidationreports["validation_report_id"] = featurevalidationreports["validation_id"].replace(
        validationreport_id_to_name
    )
    featurevalidationreports["feature_name"] = featurevalidationreports["feature"]
    dfs["validation_report_features"] = featurevalidationreports.drop(columns=["validation_id", "feature"])
    del dfs["featurevalidationreport"]

    notices = dfs.get("notice")
    notices["dataset_id"] = notices["dataset_id"].replace(dataset_id_to_stable_id)
    notices["validation_report_id"] = notices["validation_report_id"].replace(validationreport_id_to_name)
    dfs["notices"] = notices
    del dfs["notice"]

    del dfs["feedreference"]
    del dfs["location"]
    del dfs["locationfeed"]
    del dfs["externalid"]
    del dfs["gtfsdataset"]
    del dfs["redirectingid"]
    del dfs["validationreportgtfsdataset"]
    del dfs["feed"]

    for table, df in dfs.items():
        if df.shape[0] > 0:
            # Convert the DataFrame into a JSON object and add it to the data dictionary
            records = df.to_dict(orient="records")
            data[table] = [{k: v for k, v in record.items() if v is not None} for record in records]

    # Write the data dictionary to a JSON file
    with open(file_name, "w") as f:
        json.dump(data, f, cls=CustomEncoder)


def is_test_db(url):
    return url is None or "MobilityDatabaseTest" in url


excluded_tables: Final[list[str]] = [
    "databasechangelog",
    "databasechangeloglock",
    "geography_columns",
    "geometry_columns",
    "spatial_ref_sys",
    # Excluding the views
    "feedsearch",
    "location_with_translations_en",
]


def empty_database(db, url):
    if is_test_db(url):

        metadata_tables = Base.metadata.tables

        # Get all table names excluding those in the excluded_tables list
        all_table_names = [table_name for table_name in metadata_tables.keys() if table_name not in excluded_tables]

        # Sort the table names in reverse order of dependencies
        tables_to_delete = sorted(
            all_table_names, key=lambda name: len(metadata_tables[name].foreign_keys), reverse=True
        )

        try:
            with db.start_db_session() as session:
                for table_name in tables_to_delete:
                    table = Base.metadata.tables[table_name]
                    delete_stmt = delete(table)
                    session.execute(delete_stmt)

        except Exception as error:
            logging.error(f"Error while deleting from test db: {error}")
