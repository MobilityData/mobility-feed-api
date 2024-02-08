import numpy as np


def set_up_defaults(df):
    """
    Updates the dataframe to match types defined in the database
    @param df: Dataframe to update
    """
    df.status = df.status.fillna("active")
    df["urls.authentication_type"] = df["urls.authentication_type"].fillna(0)
    df["features"] = df["features"].fillna("")
    df["entity_type"] = df["entity_type"].fillna("")
    df["location.country_code"] = df["location.country_code"].fillna("")
    df["location.subdivision_name"] = df["location.subdivision_name"].fillna("")
    df["location.municipality"] = df["location.municipality"].fillna("")
    df = df.replace(np.nan, None)
    df = df.replace("gtfs-rt", "gtfs_rt")
    df["location.country_code"] = df["location.country_code"].replace("unknown", "")
    df["location.subdivision_name"] = df["location.subdivision_name"].replace("unknown", "")
    df["location.municipality"] = df["location.municipality"].replace("unknown", "")
    return df
