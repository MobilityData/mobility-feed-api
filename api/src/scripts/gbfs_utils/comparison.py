import pandas as pd
from sqlalchemy.orm import joinedload
from shared.database_gen.sqlacodegen_models import Gbfsfeed


def generate_system_csv_from_db(df, db_session):
    """Generate a DataFrame from the database with the same columns as the CSV file."""
    query = db_session.query(Gbfsfeed)
    query = query.options(
        joinedload(Gbfsfeed.locations), joinedload(Gbfsfeed.gbfsversions), joinedload(Gbfsfeed.externalids)
    )
    feeds = query.all()
    data = []
    for feed in feeds:
        system_id = feed.externalids[0].associated_id
        auto_discovery_url = feed.auto_discovery_url
        feed.gbfsversions.sort(key=lambda x: x.version, reverse=False)
        supported_versions = [version.version for version in feed.gbfsversions]
        data.append(
            {
                "System ID": system_id,
                "Name": feed.operator,
                "URL": feed.operator_url,
                "Country Code": feed.locations[0].country_code,
                "Location": feed.locations[0].municipality,
                "Auto-Discovery URL": auto_discovery_url,
                "Supported Versions": " ; ".join(supported_versions),
            }
        )
    if not data:
        # Return an empty DataFrame with the same columns
        return pd.DataFrame(columns=df.columns)
    return pd.DataFrame(data)


def compare_db_to_csv(df_from_db, df_from_csv, logger):
    """Compare the database to the CSV file and return the differences."""
    df_from_csv = df_from_csv[df_from_db.columns]
    df_from_db = df_from_db.fillna("")
    df_from_csv = df_from_csv.fillna("")

    df_from_db = df_from_db.drop(columns=["Supported Versions"])
    df_from_csv = df_from_csv.drop(columns=["Supported Versions"])

    if df_from_db.empty:
        logger.info("No data found in the database.")
        return None, None

    # Align both DataFrames by "System ID"
    # Keep the System ID column because it's used later in the code
    df_from_db.set_index("System ID", inplace=True, drop=False)
    df_from_csv.set_index("System ID", inplace=True, drop=False)

    # Find rows that are in the CSV but not in the DB (new feeds)
    missing_in_db = df_from_csv[~df_from_csv.index.isin(df_from_db.index)]
    if not missing_in_db.empty:
        logger.info("New feeds found in CSV:")
        logger.info(missing_in_db)

    # Find rows that are in the DB but not in the CSV (deprecated feeds)
    missing_in_csv = df_from_db[~df_from_db.index.isin(df_from_csv.index)]
    if not missing_in_csv.empty:
        logger.info("Deprecated feeds found in DB:")
        logger.info(missing_in_csv)

    # Find rows that are in both, but with differences
    common_ids = df_from_db.index.intersection(df_from_csv.index)
    df_db_common = df_from_db.loc[common_ids]
    df_csv_common = df_from_csv.loc[common_ids]

    # Exclude 'Location' from comparison because the DB values might have been changed in the
    # python function that calculates the location.
    columns_to_compare = [col for col in df_db_common.columns if col != "Location"]
    differences = df_db_common[columns_to_compare] != df_csv_common[columns_to_compare]
    differing_rows = df_csv_common[differences.any(axis=1)]

    if not differing_rows.empty:
        logger.info("Rows with differences:")
        for idx in differing_rows.index:
            logger.info(f"Differences for System ID {idx}:")
            db_row = df_db_common.loc[idx]
            csv_row = df_csv_common.loc[idx]
            diff = db_row != csv_row
            logger.info(f"DB Row: {db_row[diff].to_dict()}")
            logger.info(f"CSV Row: {csv_row[diff].to_dict()}")
            logger.info(80 * "-")

    # Merge differing rows with missing_in_db to capture all new or updated feeds
    # Drop the index because we have it as the System ID column.
    all_differing_or_new_rows = pd.concat([differing_rows, missing_in_db]).reset_index(drop=True)

    return all_differing_or_new_rows, missing_in_csv
