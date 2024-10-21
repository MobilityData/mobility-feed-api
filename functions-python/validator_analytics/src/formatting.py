import logging

import pandas as pd
import math


def create_dropdown_for_severity(sheet_id: int, df: pd.DataFrame, start_column_index: int = 0) -> list:
    """
    Create data validation for the 'Severity' column, adding a dropdown with the options 'INFO', 'WARNING', 'ERROR'.
    :param sheet_id: The ID of the sheet.
    :param df: The DataFrame to apply the validation.
    :param start_column_index: The starting index of the 'Severity' column.
    :return: A list of requests for Google Sheets API.
    """
    # Get the index of the 'Severity' column
    severity_column_index = start_column_index + df.columns.get_loc("Severity")

    # Define the data validation rule (dropdown)
    data_validation_rule = {
        "setDataValidation": {
            "range": {
                "sheetId": sheet_id,
                "startRowIndex": 1,  # Assuming the first row is the header
                "endRowIndex": len(df) + 1,
                "startColumnIndex": severity_column_index,
                "endColumnIndex": severity_column_index + 1,
            },
            "rule": {
                "condition": {
                    "type": "ONE_OF_LIST",
                    "values": [
                        {"userEnteredValue": "INFO"},
                        {"userEnteredValue": "WARNING"},
                        {"userEnteredValue": "ERROR"}
                    ]
                },
                "showCustomUi": True,  # Show as a dropdown in the UI
                "strict": True  # Strict validation (only allow these values)
            }
        }
    }

    return [data_validation_rule]

def apply_dropdown_validation(service, spreadsheet_id, sheet_id, df, start_column_index=0):
    # Create the dropdown data validation requests
    dropdown_requests = create_dropdown_for_severity(sheet_id, df, start_column_index)

    # Batch update the requests
    body = {"requests": dropdown_requests}
    service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body=body
    ).execute()


def calculate_column_widths(df, extra_width=50, char_width=5):
    """
    Calculate the pixel width for each column based on the longest cell value.
    :param df: DataFrame containing the data.
    :param extra_width: Additional width (in pixels) to add to the calculated width.
    :param char_width: Approximate width of a character in pixels.
    :return: A list of column widths.
    """
    column_widths = []

    for col in df.columns:
        # Get the length of the longest string representation in the column
        max_length = max(df[col].astype(str).map(len).max(), len(str(col)))
        # Consider the width of the column header
        max_length = max(max_length, len(str(col)))
        pixel_width = math.ceil(max_length * char_width) + extra_width
        column_widths.append(pixel_width)

    return column_widths


def create_formatting_requests(df: pd.DataFrame, sheet_id: int, start_column_index: int = 0, gradient_columns=["New Notices", "Dropped Notices"]) -> list:
    """
    Create formatting requests for the Google Sheets API for a given table.
    :param df: The DataFrame containing the data to format.
    :param sheet_id: The ID of the sheet to format.
    :param start_column_index: The starting column index for where the table is placed.
    :param gradient_columns: The columns to apply gradient formatting.
    :return: A list of formatting requests.
    """
    assert gradient_columns is not None and len(gradient_columns) == 2, "Gradient columns must contain exactly 2 columns"

    # Create the requests for setting the width of each column
    column_widths = calculate_column_widths(df)
    dimension_properties_requests = [
        {
            "updateDimensionProperties": {
                "range": {
                    "sheetId": sheet_id,
                    "dimension": "COLUMNS",
                    "startIndex": start_column_index + i,
                    "endIndex": start_column_index + i + 1,
                },
                "properties": {"pixelSize": width},
                "fields": "pixelSize",
            }
        }
        for i, width in enumerate(column_widths)
    ]
    logging.info(f"Column widths: {column_widths}")
    logging.info(df)
    logging.info(f"End column index: {start_column_index + len(df.columns)}")
    return [
        {
            "repeatCell": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": 0,
                    "endRowIndex": len(df) + 1,
                    "startColumnIndex": start_column_index,
                    "endColumnIndex": start_column_index + len(df.columns),
                },
                "cell": {
                    "userEnteredFormat": {
                        "textFormat": {"fontFamily": "Muli"},
                        "borders": {
                            "top": {"style": "SOLID"},
                            "bottom": {"style": "SOLID"},
                            "left": {"style": "SOLID"},
                            "right": {"style": "SOLID"},
                        },
                    }
                },
                "fields": "userEnteredFormat(horizontalAlignment,borders,textFormat)",
            }
        },
        {
            "repeatCell": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": 0,
                    "endRowIndex": 1,
                    "startColumnIndex": start_column_index,
                    "endColumnIndex": start_column_index + len(df.columns),
                },
                "cell": {"userEnteredFormat": {"textFormat": {"bold": True}}},
                "fields": "userEnteredFormat(textFormat)",
            }
        },
        # Apply conditional formatting for severity values in the 'Severity' column
        {
            "addConditionalFormatRule": {
                "rule": {
                    "ranges": [
                        {
                            "sheetId": sheet_id,
                            "startRowIndex": 1,
                            "endRowIndex": len(df) + 1,
                            "startColumnIndex": start_column_index + df.columns.get_loc("Severity"),
                            "endColumnIndex": start_column_index + df.columns.get_loc("Severity") + 1,
                        }
                    ],
                    "booleanRule": {
                        "condition": {"type": "TEXT_EQ", "values": [{"userEnteredValue": "INFO"}]},
                        "format": {
                            "backgroundColorStyle": {"rgbColor": {"red": 0.89, "green": 0.89, "blue": 1.0}},
                        },
                    },
                },
                "index": 0,
            }
        },
        {
            "addConditionalFormatRule": {
                "rule": {
                    "ranges": [
                        {
                            "sheetId": sheet_id,
                            "startRowIndex": 1,
                            "endRowIndex": len(df) + 1,
                            "startColumnIndex": start_column_index + df.columns.get_loc("Severity"),
                            "endColumnIndex": start_column_index + df.columns.get_loc("Severity") + 1,
                        }
                    ],
                    "booleanRule": {
                        "condition": {"type": "TEXT_EQ", "values": [{"userEnteredValue": "WARNING"}]},
                        "format": {
                            "backgroundColorStyle": {"rgbColor": {"red": 0.98, "green": 0.92, "blue": 0.73}}
                        },
                    },
                },
                "index": 1,
            }
        },
        {
            "addConditionalFormatRule": {
                "rule": {
                    "ranges": [
                        {
                            "sheetId": sheet_id,
                            "startRowIndex": 1,
                            "endRowIndex": len(df) + 1,
                            "startColumnIndex": start_column_index + df.columns.get_loc("Severity"),
                            "endColumnIndex": start_column_index + df.columns.get_loc("Severity") + 1,
                        }
                    ],
                    "booleanRule": {
                        "condition": {"type": "TEXT_EQ", "values": [{"userEnteredValue": "ERROR"}]},
                        "format": {
                            "backgroundColorStyle": {"rgbColor": {"red": 0.96, "green": 0.83, "blue": 0.8}}
                        },
                    },
                },
                "index": 2,
            }
        },
        # Apply gradient formatting
        {
            "addConditionalFormatRule": {
                "rule": {
                    "ranges": [
                        {
                            "sheetId": sheet_id,
                            "startRowIndex": 1,
                            "endRowIndex": len(df) + 1,
                            "startColumnIndex": start_column_index + df.columns.get_loc(gradient_columns[0]),
                            "endColumnIndex": start_column_index + df.columns.get_loc(gradient_columns[0]) + 1,
                        }
                    ],
                    "gradientRule": {
                        "minpoint": {
                            "colorStyle": {"rgbColor": {"red": 1.0, "green": 1.0, "blue": 1.0}},
                            "type": "NUMBER",
                            "value": "0",
                        },
                        "maxpoint": {
                            "colorStyle": {"rgbColor": {"red": 0.8, "green": 0.2, "blue": 0.2, "alpha": 0.5}},
                            "type": "NUMBER",
                            "value": "100",
                        },
                    },
                },
                "index": 0,
            }
        },
        {
            "addConditionalFormatRule": {
                "rule": {
                    "ranges": [
                        {
                            "sheetId": sheet_id,
                            "startRowIndex": 1,
                            "endRowIndex": len(df) + 1,
                            "startColumnIndex": start_column_index + df.columns.get_loc(gradient_columns[1]),
                            "endColumnIndex": start_column_index + df.columns.get_loc(gradient_columns[1]) + 1,
                        }
                    ],
                    "gradientRule": {
                        "minpoint": {
                            "colorStyle": {"rgbColor": {"red": 1.0, "green": 1.0, "blue": 1.0}},
                            "type": "NUMBER",
                            "value": "0",
                        },
                        "maxpoint": {
                            "colorStyle": {"rgbColor": {"red": 0.8, "green": 0.2, "blue": 0.2, "alpha": 0.5}},
                            "type": "NUMBER",
                            "value": "100",
                        },
                    },
                },
                "index": 1,
            }
        },
    ] + dimension_properties_requests
