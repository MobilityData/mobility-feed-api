# GitHub Workflows Overview (Hierarchical)

This folder contains GitHub Actions workflows. Below is a concise, hierarchical catalog: what each workflow does (plain English) and how it’s triggered or called.

## Database (DB)
- [db-update.yml](https://github.com/MobilityData/mobility-feed-api/blob/main/.github/workflows/db-update.yml)
  - Description: updates the database schema (Liquibase). It does not apply content updates.
  - Called by:
    - [db-update-dev.yml](https://github.com/MobilityData/mobility-feed-api/blob/main/.github/workflows/db-update-dev.yml)
      - Description: Runs DB schema updates for DEV.
      - Trigger: Manual run.
    - [db-update-qa.yml](https://github.com/MobilityData/mobility-feed-api/blob/main/.github/workflows/db-update-qa.yml)
      - Description: Runs DB schema updates for QA.
      - Trigger: Manual run and call from release-qa.yml.
    - [db-update-prod.yml](https://github.com/MobilityData/mobility-feed-api/blob/main/.github/workflows/db-update-prod.yml)
      - Description: Runs DB schema updates for PROD.
      - Trigger: Manual run and call from release.yml.

- [db-update-content.yml](https://github.com/MobilityData/mobility-feed-api/blob/main/.github/workflows/db-update-content.yml)
  - Description: Applies DB content updates (data population/maintenance). Does not modify the DB schema.
  - Called by:
    - [catalog-update.yml](https://github.com/MobilityData/mobility-feed-api/blob/main/.github/workflows/catalog-update.yml)
      - Description: Update all the environment DB contents if there is a change in data in the [mobility-database-catalogs](https://github.com/MobilityData/mobility-database-catalogs) repository.
      - Trigger: Manual run or dispatch from mobility-database-catalog repository.

- [duplicate-prod-db.yml](https://github.com/MobilityData/mobility-feed-api/blob/main/.github/workflows/duplicate-prod-db.yml)
  - Description: Duplicates the prod DB contents to the QA environment.
  - Trigger: Manual or during a prerelease.

## Release
- [release-qa.yml](https://github.com/MobilityData/mobility-feed-api/blob/main/.github/workflows/release-qa.yml)
  - Description: Coordinates a QA release.
  - Trigger: Manual or it's invoked each time a PR is merged.

- [release.yml](https://github.com/MobilityData/mobility-feed-api/blob/main/.github/workflows/release.yml)
  - Description: Coordinates a release to production.
  - Trigger: Invoked when a release is done.

- [assign_next_release_milestone.yml](https://github.com/MobilityData/mobility-feed-api/blob/main/.github/workflows/assign_next_release_milestone.yml)
  - Description: Assigns GitHub issues/PRs to the next release milestone.
  - Trigger: On PR merge or manual run.

## Web
- [web-app-deployer.yml](https://github.com/MobilityData/mobility-feed-api/blob/main/.github/workflows/web-app-deployer.yml)
  - Description: build and deploy the web application.
  - Called by:
    - [web-dev.yml](https://github.com/MobilityData/mobility-feed-api/blob/main/.github/workflows/web-dev.yml)
      - Description: Deploys web app to DEV.
      - Trigger: Manual run.
    - [web-qa.yml](https://github.com/MobilityData/mobility-feed-api/blob/main/.github/workflows/web-qa.yml)
      - Description: Deploys web app to QA.
      - Trigger: Manual or call from release-qa.yml.
    - [web-prod.yml](https://github.com/MobilityData/mobility-feed-api/blob/main/.github/workflows/web-prod.yml)
      - Description: Deploys web app to Production.
      - Trigger: Manual or call from release.yml.
    - [web-pr.yml](https://github.com/MobilityData/mobility-feed-api/blob/main/.github/workflows/web-pr.yml)
      - Description: Builds/previews web app for pull requests.
      - Trigger: When a commit is added to a pull request for files that affects the web app.
    - [web-prototype.yml](https://github.com/MobilityData/mobility-feed-api/blob/main/.github/workflows/web-prototype.yml)
      - Description: Builds/deploys prototype web app.
      - Trigger: Manual run.

## API
- [api-deployer.yml](https://github.com/MobilityData/mobility-feed-api/blob/main/.github/workflows/api-deployer.yml)
  - Description: Build and deploy the API service.
  - Called by:
    - [api-dev.yml](https://github.com/MobilityData/mobility-feed-api/blob/main/.github/workflows/api-dev.yml)
      - Description: Deploys API to DEV.
      - Trigger: Manual.
    - [api-qa.yml](https://github.com/MobilityData/mobility-feed-api/blob/main/.github/workflows/api-qa.yml)
      - Description: Deploys API to QA.
      - Trigger:       - Trigger: Manual run and call from release-qa.yml.
    - [api-prod.yml](https://github.com/MobilityData/mobility-feed-api/blob/main/.github/workflows/api-prod.yml)
      - Description: Deploys API to PROD.
      - Trigger: Manual run and call from release.yml.

## Functions / Batch
- [datasets-batch-deployer.yml](https://github.com/MobilityData/mobility-feed-api/blob/main/.github/workflows/datasets-batch-deployer.yml)
  - Description: Reusable workflow to deploy datasets batch Cloud Run/Functions.
  - Called by:
    - [datasets-batch-deployer-dev.yml](https://github.com/MobilityData/mobility-feed-api/blob/main/.github/workflows/datasets-batch-deployer-dev.yml)
      - Description: Deploys batch pipelines to DEV.
      - Trigger: Manual run or `workflow_call`.
    - [datasets-batch-deployer-qa.yml](https://github.com/MobilityData/mobility-feed-api/blob/main/.github/workflows/datasets-batch-deployer-qa.yml)
      - Description: Deploys batch pipelines to QA.
      - Trigger: Manual run or `workflow_call`.
    - [datasets-batch-deployer-prod.yml](https://github.com/MobilityData/mobility-feed-api/blob/main/.github/workflows/datasets-batch-deployer-prod.yml)
      - Description: Deploys batch pipelines to PROD.
      - Trigger: Manual run or `workflow_call`.

- [validator-update.yml](https://github.com/MobilityData/mobility-feed-api/blob/main/.github/workflows/validator-update.yml)
  - Description: Updates GBFS/GTFS validators deployments.
  - Trigger: Manual run or `workflow_call`.

## Misc / CI
- [build-test.yml](https://github.com/MobilityData/mobility-feed-api/blob/main/.github/workflows/build-test.yml)
  - Description: Builds and runs unit tests for API/backend.
  - Trigger: When a commit is added to a PR and called by api-deployer.yml.

- [integration-tests.yml](https://github.com/MobilityData/mobility-feed-api/blob/main/.github/workflows/integration-tests.yml)
  - Description: Runs integration tests across services.
  - Trigger: Push/PR or manual run.

- [integration-tests-pr.yml](https://github.com/MobilityData/mobility-feed-api/blob/main/.github/workflows/integration-tests-pr.yml)
  - Description: Executes integration tests for pull requests.
  - Trigger: PR events.

- [schedule-load-test.yml](https://github.com/MobilityData/mobility-feed-api/blob/main/.github/workflows/schedule-load-test.yml)
  - Description: Scheduled load/performance tests.
  - Trigger: `schedule` (cron) and manual run.

- [typescript-generator-check.yml](https://github.com/MobilityData/mobility-feed-api/blob/main/.github/workflows/typescript-generator-check.yml)
  - Description: Verifies TypeScript types generation for API.
  - Trigger: Push/PR affecting OpenAPI or web types.

- [typescript-generator-gbfs-validator-types-check.yml](https://github.com/MobilityData/mobility-feed-api/blob/main/.github/workflows/typescript-generator-gbfs-validator-types-check.yml)
  - Description: Validates generated TS types for GBFS Validator.
  - Trigger: Push/PR affecting GBFS validator schema or types.

Notes
- Workflows are loaded only if placed directly in `.github/workflows` with `.yml/.yaml` extension.
- Reusable workflows are invoked with `uses: ./.github/workflows/<file>.yml` from caller workflows.
