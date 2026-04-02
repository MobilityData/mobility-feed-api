# GTFS validator orchestrator

## Context
Around two times per year the GTFS validators is released. On every release we assests the impact on current feeds. The process is:
1. Calling the update-validation-report GCP function to generate all the validation report before the GTFS validator is released. This is done by passing the validator_endpoint with staging URL and env staging
Example call:
```shel
curl -X POST "https://northamerica-northeast1-mobility-feeds-prod.cloudfunctions.net/update-validation-report" \
-H "Authorization: bearer $(gcloud auth print-identity-token)" \
-H "Content-Type: application/json" \
-d '{
    "validator_endpoint": "https://gtfs-validator-staging.mobilitydata.org/api",
    "force_update": false,
    "env": "staging"
}'
```
2. Call big_query_ingestion GCP function. This function ingests the reports to BigQuery.

## Challenges

1. The update-validation-report don't have a parameter to execute on "dry_run". This is useful to get a sense on how many reports will be generated without actually generating the reports.
2. As the number of feeds had increased the update-validation-report function is timing out before all the workflow executions are triggered. If the function is called again it will start from the beggining and will time out again and waste a lot of resources creating the validation report again.
3. The update-validation-report doesn't follow-up in the workflow executions. After all the executions are sent, it returns the response without waiting for the all executions to finish.


## Tasks
- I need to add dry-tun parameter to the update-validation-report function.
- Move the update-validation-report function to the tasks_executor folder and have a tasks for it. Removing the need of an independent function.
- Find a way to keep track of the execution
- Allow to monitor the process end to end. A long running process is too much as they are around 5000 feeds to process
- We need to make sure the full process works from generating the validation report to the call to validation_to_ndjson to ingest to Bigquery
