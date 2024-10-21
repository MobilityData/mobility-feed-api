#
#   MobilityData 2024
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#

import logging
import bigframes as bf
import bigframes.pandas as bpd
import functions_framework
import google.auth
import pandas as pd
from googleapiclient.discovery import build
from helpers.logger import Logger
from .formatting import create_formatting_requests, apply_dropdown_validation

logging.basicConfig(level=logging.INFO)
PROJECT_ID = "mobility-feeds-dev"
DATASET_NAME = "data_analytics"
LOCATION = "northamerica-northeast1"
TABLE = "gtfs_validation_reports_*"
VALIDATION_REPORT_TABLE = f"{PROJECT_ID}.{DATASET_NAME}.{TABLE}"
PREVIOUS_VALIDATOR_VERSION = "5.0.1"
NEXT_VALIDATOR_VERSION = "5.0.2-SNAPSHOT"
SPREADSHEET_ID = "1boQYc0v3amCCql9f6toBwtGrs8vMYFM1g7dahzoEtFk"


def get_validator_analytics():
    bf.options.bigquery.project = PROJECT_ID
    bf.options.bigquery.location = LOCATION
    validation_report_df = bpd.read_gbq(VALIDATION_REPORT_TABLE)

    # Filter to the most recent dataset for each feed
    def get_most_recent_datasets(df, validation_version):
        mask = [
            validation_version == summary["validatorVersion"]
            for summary in df["summary"]
        ]
        filtered_df = df[bf.series.Series(mask, index=df.index)]
        df_sorted = filtered_df.sort_values(
            by=["feedId", "validatedAt"], ascending=[True, False]
        )
        return df_sorted.drop_duplicates(subset="feedId", keep="first")

    most_recent_reports = get_most_recent_datasets(
        validation_report_df, NEXT_VALIDATOR_VERSION
    )
    old_version_reports = get_most_recent_datasets(
        validation_report_df, PREVIOUS_VALIDATOR_VERSION
    )

    def process_notices(df):
        exploded_notices_df = df.explode("notices")
        exploded_notices_df = exploded_notices_df[
            exploded_notices_df["notices"].notna()
        ].reset_index(drop=True)
        normalized_notices = pd.json_normalize(exploded_notices_df["notices"])
        normalized_notices[["feedId", "datasetId"]] = exploded_notices_df[
            ["feedId", "datasetId"]
        ]
        return normalized_notices

    most_recent_reports_normalized = process_notices(most_recent_reports)
    old_version_reports_normalized = process_notices(old_version_reports)

    def merge_dataframes(df1, df2):
        merged_df = pd.merge(
            df1,
            df2,
            on=["feedId", "code"],
            how="outer",
            suffixes=("_previous", "_current"),
        )
        return merged_df

    merged_dfs = merge_dataframes(
        old_version_reports_normalized, most_recent_reports_normalized
    )
    merged_dfs["totalNotices_previous"] = merged_dfs["totalNotices_previous"].fillna(0)
    merged_dfs["totalNotices_current"] = merged_dfs["totalNotices_current"].fillna(0)

    merged_dfs["New Notices"] = (
        merged_dfs["totalNotices_current"] - merged_dfs["totalNotices_previous"]
    )
    merged_dfs["Dropped Notices"] = (
        merged_dfs["totalNotices_current"] - merged_dfs["totalNotices_previous"]
    )
    merged_dfs.loc[merged_dfs["New Notices"] < 0, "New Notices"] = 0
    merged_dfs.loc[merged_dfs["Dropped Notices"] > 0, "Dropped Notices"] = 0
    merged_dfs["Dropped Notices"] = merged_dfs["Dropped Notices"].abs()
    result_df = merged_dfs[
        [
            "feedId",
            "code",
            "severity_previous",
            "severity_current",
            "New Notices",
            "Dropped Notices",
        ]
    ]
    result_df.loc[:, "severity_previous"] = result_df["severity_previous"].fillna(
        result_df["severity_current"]
    )
    result_df = result_df.drop(columns=["severity_current"])

    result_df = result_df.rename(
        columns={
            "feedId": "Feed ID",
            "code": "Code",
            "severity_previous": "Severity",
        }
    )
    # Sort the results in descending order by 'New Notices' and 'Dropped Notices'
    result_df = result_df.sort_values(
        by=["New Notices", "Dropped Notices"], ascending=[False, False]
    )

    return result_df


def get_column_letter(n):
    """
    Convert a column index (starting from 1) to a Google Sheets-style letter (A, B, ..., AA, AB, ...).
    :param n: The column index (1-based)
    :return: The corresponding column letter(s)
    """
    result = ""
    while n > 0:
        n, remainder = divmod(n - 1, 26)
        result = chr(65 + remainder) + result
    return result


def get_sheet_range(df, sheet_name="Sheet1", start_cell="A1"):
    """
    Compute the Google Sheets range based on the size of the DataFrame.
    :param df: DataFrame to upload
    :param sheet_name: Name of the sheet
    :param start_cell: Starting cell for the range
    :return: String representing the range in A1 notation
    """
    num_rows, num_cols = df.shape  # Get number of rows and columns
    skipped_columns = ord(start_cell[0]) - ord("A")
    start_column, start_row = start_cell[0], int(start_cell[1:])
    end_column = get_column_letter(num_cols + skipped_columns)
    end_row = start_row + num_rows - 1
    return f"'{sheet_name}'!{start_column}{start_row}:{end_column}{end_row + 1}"


def create_aggregated_table(df):
    """
    Create an aggregated table that groups the original DataFrame by 'Code'
    and calculates the number of feeds with dropped and added notices.
    :param df: Original DataFrame with validation analytics.
    :return: Aggregated DataFrame.
    """
    # Count feeds with dropped notices (Dropped Notices > 0)
    df["Has Dropped Notices"] = df["Dropped Notices"] > 0
    df["Has New Notices"] = df["New Notices"] > 0

    aggregated_df = df.groupby(["Code", "Severity"]).agg(
        Feeds_With_Dropped_Notices=("Has Dropped Notices", "sum"),
        Feeds_With_New_Notices=("Has New Notices", "sum"),
    ).reset_index()

    # Sort by the counts of feeds with dropped and new notices
    aggregated_df = aggregated_df.sort_values(
        by=["Feeds_With_New_Notices", "Feeds_With_Dropped_Notices"],
        ascending=[False, False]
    )
    result_df = aggregated_df[
        ['Code', 'Severity','Feeds_With_New_Notices', 'Feeds_With_Dropped_Notices']
    ].rename(
        columns={
            "Code": "Code",
            "Severity": "Severity",
            "Feeds_With_New_Notices": "Feeds w/New Notices",
            "Feeds_With_Dropped_Notices": "Feeds w/Dropped Notices",
        }
    )
    # Drop created columns in the original DataFrame
    df.drop(columns=["Has Dropped Notices", "Has New Notices"], inplace=True)

    return result_df


@functions_framework.http
def generate_validator_analytics(request):
    """
    Generate comparison analytics for the given validator versions.
    It expects a JSON request body with the following fields:
    - 'previous_version': the previous validator version
    - 'current_version': the current validator version
    :param request: Request object containing 'dataset_id' and 'feed_id'
    :return: HTTP response indicating the result of the operation
    """
    Logger.init_logger()
    request_json = request.get_json(silent=True)
    logging.info(
        f"Gathering analytics for validator versions {request_json.get('previous_version')} and "
        f"{request_json.get('current_version')}."
    )

    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds, project = google.auth.default(scopes=scopes)
    service = build("sheets", "v4", credentials=creds)

    # Clear the existing data in the sheet if it exists
    sheet_name = f"{PREVIOUS_VALIDATOR_VERSION} vs {NEXT_VALIDATOR_VERSION}"
    try:
        response = (
            service.spreadsheets()
            .values()
            .clear(
                spreadsheetId=SPREADSHEET_ID,
                range=sheet_name,
                body={},
            )
            .execute()
        )

        logging.info(f"Clear response: {response}")
        # Get the sheet ID
        sheet_metadata = (
            service.spreadsheets().get(spreadsheetId=SPREADSHEET_ID).execute()
        )
        sheet = sheet_metadata["sheets"]
        sheet_id = 0
        for item in sheet:
            if item["properties"]["title"] == sheet_name:
                sheet_id = item["properties"]["sheetId"]
                break
        logging.info(f"Sheet ID: {sheet_id}")

        #  Clear the formatting
        try:
            requests = [
                {
                    "deleteConditionalFormatRule": {
                        "sheetId": sheet_id,
                    }
                },
                {
                    "updateCells": {
                        "range": {"sheetId": sheet_id},
                        "fields": "userEnteredFormat",
                    }
                },
            ]
            body = {"requests": requests}
            service.spreadsheets().batchUpdate(
                spreadsheetId=SPREADSHEET_ID, body=body
            ).execute()
        except Exception:
            logging.info("No formatting to clear.")
    except Exception:
        # If the sheet does not exist, create it
        add_sheet_request = {
            "addSheet": {
                "properties": {
                    "title": sheet_name,
                }
            }
        }
        body = {"requests": [add_sheet_request]}
        response = (
            service.spreadsheets()
            .batchUpdate(spreadsheetId=SPREADSHEET_ID, body=body)
            .execute()
        )
        logging.info(f"Add sheet response: {response}")
        sheet_id = response["replies"][0]["addSheet"]["properties"]["sheetId"]
        logging.info(f"Sheet ID: {sheet_id}")

    # Get the initial DataFrame and fill NA values with empty strings for upload
    df = get_validator_analytics()
    df = df.fillna("")
    values = [df.columns.tolist()] + df.values.tolist()

    # Define the range for the initial table
    range_1 = get_sheet_range(df, sheet_name)
    body = {"values": values}

    result = (
        service.spreadsheets()
        .values()
        .update(
            spreadsheetId=SPREADSHEET_ID,
            range=range_1,
            valueInputOption="RAW",
            body=body,
        )
        .execute()
    )

    logging.info(f"Update result for initial table: {result}")

    # Create the aggregated table
    aggregated_df = create_aggregated_table(df)
    aggregated_values = [aggregated_df.columns.tolist()] + aggregated_df.values.tolist()

    # Define the range for the aggregated table (to the right of the initial table)
    range_2 = get_sheet_range(aggregated_df, sheet_name, "G1")
    body = {"values": aggregated_values}
    result = (
        service.spreadsheets()
        .values()
        .update(
            spreadsheetId=SPREADSHEET_ID,
            range=range_2,
            valueInputOption="RAW",
            body=body,
        )
        .execute()
    )

    logging.info(f"Update result for aggregated table: {result}")

    # Generate formatting requests using the extracted function
    requests = create_formatting_requests(df, sheet_id)
    apply_dropdown_validation(service, SPREADSHEET_ID, sheet_id, df)
    apply_dropdown_validation(service, SPREADSHEET_ID, sheet_id, aggregated_df, ord("G") - ord("A"))
    requests += create_formatting_requests(aggregated_df, sheet_id, ord("G") - ord("A"), gradient_columns=["Feeds w/New Notices", "Feeds w/Dropped Notices"])
    body = {"requests": requests}

    service.spreadsheets().batchUpdate(
        spreadsheetId=SPREADSHEET_ID, body=body
    ).execute()

    print("Hello!")
    return "Hello!"
