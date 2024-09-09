import json
from google.cloud import bigquery


json_schema_map = {
    "gtfs": "gtfs_schema.json",
    "gbfs": "gbfs_schema.json",
}


def json_schema_to_bigquery(json_schema):
    def convert_field(field):
        name = field["name"]
        field_type = field["type"].upper()

        mode = field.get("mode", "NULLABLE")  # Default mode is NULLABLE

        # Handle nested fields for RECORD types
        if field_type == "RECORD":
            subfields = [
                convert_field(subfield) for subfield in field.get("fields", [])
            ]
            return bigquery.SchemaField(name, field_type, mode=mode, fields=subfields)
        else:
            return bigquery.SchemaField(name, field_type, mode=mode)

    return [convert_field(field) for field in json_schema.get("fields", [])]


def filter_json_by_schema(json_schema, input_json):
    def filter_fields(fields, data):
        filtered_data = {}
        for field in fields:
            field_name = field["name"]
            field_type = field["type"]
            field_mode = field.get(
                "mode", "NULLABLE"
            )  # Default mode is NULLABLE if not specified

            if field_name in data:
                if field_type == "RECORD" and "fields" in field:
                    if field_mode == "REPEATED":
                        # Handle repeated RECORDS
                        filtered_data[field_name] = [
                            filter_fields(field["fields"], item)
                            for item in data[field_name]
                        ]
                    else:
                        # Handle single RECORD
                        filtered_data[field_name] = filter_fields(
                            field["fields"], data[field_name]
                        )
                else:
                    # Handle simple field types
                    filtered_data[field_name] = data[field_name]
        return filtered_data

    if "fields" in json_schema:
        return filter_fields(json_schema["fields"], input_json)
    else:
        raise ValueError("Invalid schema format")


def load_json_schema(json_schema_path):
    # Read the JSON schema file into a Python dictionary
    with open(json_schema_path, "r") as schema_file:
        json_schema = json.load(schema_file)
    return json_schema
