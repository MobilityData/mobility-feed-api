# Validator releases

What the Mobility Database does when a new version of a validator is released, and what to check.

## GTFS validator

### Before the release

Comparing the new version with the last release is done in the gtfs-validator repository, with its acceptance tests (see its [release steps](https://github.com/MobilityData/gtfs-validator/blob/master/docs/RELEASE.md)). Nothing to do in this repository.

### What happens automatically

1. Publishing a gtfs-validator release (not a pre-release) deploys the production web validator and sends the `gtfs-validator-release` repository dispatch to this repository.
2. [`validator-update.yml`](../.github/workflows/validator-update.yml) creates a Cloud Task in the `validator-update-trigger-queue` queue, scheduled 24 hours later, so that the web validator has been updated everywhere.
3. The task runs [`rebuild_missing_validation_reports`](../functions-python/tasks_executor/src/tasks/validation_reports/README.md) in production with `force_update: true`: the latest dataset of every published feed is validated again with the new version. The API and the website then show the new report, the one with the highest validator version; the previous reports are kept.
4. `sync_task_run_status` follows the run every 10 minutes until every dataset is done.

Datasets downloaded after the release are validated with the new version as they arrive. The new reports reach BigQuery with the monthly ingestion, on the 2nd of each month.

### Checks

1. The day of the release: the `validator-update.yml` run succeeded. A failure is also sent to Slack.
2. From 24 hours after the release: the run's progress, by calling the `tasks_executor` function with:
   ```json
   {
     "task": "sync_task_run_status",
     "payload": {"task_name": "gtfs_validation", "run_id": "<new version, e.g. 8.1.0>"}
   }
   ```
   The run is done when `ready_for_bigquery` is `true`. `failed_entity_ids` lists the datasets that failed.
3. A few feeds on the website show a validation report from the new version.

### If something went wrong

- **The `validator-update.yml` run failed or did not run:** run it manually from the Actions tab. It also waits 24 hours. To start right away, call the `tasks_executor` function with:
  ```json
  {
    "task": "rebuild_missing_validation_reports",
    "payload": {"dry_run": false, "force_update": true}
  }
  ```
- **Some datasets failed, or `dispatch_complete` is `false`:** call `rebuild_missing_validation_reports` again with the same payload. Datasets already done are skipped, and failed ones are retried.

## GBFS validator

Nothing to do. Every non-deprecated GBFS feed is validated each day, Monday to Saturday, with the hosted [GBFS validator](https://gbfs-validator.mobilitydata.org/), so a new version is used from the next day. Each report records the version that produced it.
