from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas
from rich.table import Table

from endpoints.integration_tests import IntegrationTests, DatasetValidationWarning


class GTFSDatasetsEndpointTests(IntegrationTests):
    def __init__(self, file_path, access_token, url, progress, console):
        super().__init__(file_path, access_token, url, progress, console)

    def test_all_datasets(self):
        warnings = []
        with ThreadPoolExecutor(max_workers=1) as executor:
            # Prepare a list of feed IDs to process
            feed_ids = self.gtfs_feeds.mdb_source_id.values

            # Create a progress task
            task = self.progress.add_task(
                "[yellow]Validating the feeds' latest datasets...[/yellow]",
                total=len(feed_ids),
            )

            # Map each future to its feed ID
            future_to_feed_id = {
                executor.submit(self.validate_feed, feed_id): feed_id
                for feed_id in feed_ids
            }

            for future in as_completed(future_to_feed_id):
                feed_id = future_to_feed_id[future]
                warning_entry = future.result()
                if warning_entry is not None:
                    warnings.append(warning_entry)
                    self.console.log(
                        f"Feed '{warning_entry['stable_id']}' has a related [yellow]warning[/yellow]: "
                        f"{warning_entry['Warning Details']}"
                    )
                else:
                    self.console.log(
                        f"Feed 'mdb-{feed_id}' has a valid latest dataset :white_check_mark:"
                    )

                # Update the progress bar
                self.progress.update(task, advance=1)

        if warnings:
            # If there were warning, log them as before
            self._log_warnings(warnings)

    def validate_feed(self, feed_id):
        stable_id = f"mdb-{feed_id}"
        warning_detail = None
        status_code = None
        response = None
        try:
            # Validate feed response
            response = self.get_response(f"v1/feeds/{stable_id}")
            self._validate_feed_response(response)

            # Validate datasets
            response = self.get_response(
                f"v1/gtfs_feeds/{stable_id}/datasets", params={"latest": True}
            )
            datasets = response.json()
            self._validate_dataset(datasets, response.status_code)
        except Exception as e:
            warning_detail = str(e)
            if "response" in locals():
                status_code = response.status_code

            # Instead of re-raising the exception, return the warning entry directly
            return self._create_validation_report_entry(
                stable_id, warning_detail, status_code
            )

        # If the try block completes without exceptions, return None to indicate no warning
        return None

    @staticmethod
    def _validate_feed_response(response):
        if response.status_code != 200:
            warning_code = (
                DatasetValidationWarning.NOT_FOUND.name
                if response.status_code == 404
                else DatasetValidationWarning.API_ERROR.name
            )
            warning_details = (
                DatasetValidationWarning.NOT_FOUND.value
                if response.status_code == 404
                else DatasetValidationWarning.API_ERROR.value
            )
            raise Exception(f"{warning_code}: {warning_details}")

    @staticmethod
    def _validate_dataset(datasets, status_code):
        if status_code != 200 or not datasets:
            warning_code = DatasetValidationWarning.NO_DATASET.name
            warning_detail = DatasetValidationWarning.NO_DATASET.value
            raise Exception(f"{warning_code}: {warning_detail}")

    @staticmethod
    def _create_validation_report_entry(stable_id, warning_details, status_code=None):
        if warning_details is None:
            return None
        return {
            "stable_id": stable_id,
            "API Endpoint": f"v1/gtfs_feeds/{stable_id}/datasets",
            "API Response Status Code": status_code,
            "Warning Code": warning_details.split(": ")[0],
            "Warning Details": warning_details.split(": ")[1],
        }

    def _log_warnings(self, warnings):
        table = Table(
            title="Test Warnings",
            show_header=True,
            header_style="bold magenta",
            show_lines=True,
            expand=True,
        )
        table.add_column("Stable ID", style="dim")
        table.add_column("Warning Code", style="red")
        table.add_column("Warning Details", overflow="fold")
        for warning in warnings:
            table.add_row(
                warning["stable_id"],
                warning["Warning Code"],
                warning["Warning Details"],
            )
        self.console.print(table)
        pandas.DataFrame(warnings).to_csv("datasets_validation.csv")
        self.console.log(
            'Datasets validation report saved to "datasets_validation.csv"'
        )
