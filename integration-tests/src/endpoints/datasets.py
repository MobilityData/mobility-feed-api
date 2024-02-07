from concurrent.futures import ThreadPoolExecutor, as_completed

import gtfs_kit
import pandas
from rich.table import Table

from endpoints.integration_tests import IntegrationTests, FeedError


class GTFSDatasetsEndpointTests(IntegrationTests):
    def __init__(self, file_path, access_token, url, progress, console):
        super().__init__(file_path, access_token, url, progress, console)

    def test_all_datasets(self):
        errors = []
        with ThreadPoolExecutor(max_workers=3) as executor:
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
                error_entry = future.result()
                if error_entry is not None:
                    errors.append(error_entry)
                    self.console.log(
                        f"Feed '{error_entry['stable_id']}' has a related [red]error[/red]: "
                        f"{error_entry['Error Details']}"
                    )
                else:
                    self.console.log(
                        f"Feed 'mdb-{feed_id}' has a valid latest dataset :white_check_mark:"
                    )

                # Update the progress bar
                self.progress.update(task, advance=1)

        if errors:
            # If there were errors, log them as before
            self._log_errors(errors)

    def validate_feed(self, feed_id):
        stable_id = f"mdb-{feed_id}"
        error_detail = None
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
            error_detail = str(e)
            if "response" in locals():
                status_code = response.status_code

            # Instead of re-raising the exception, return the error entry directly
            return self._create_error_entry(stable_id, error_detail, status_code)

        # If the try block completes without exceptions, return None to indicate no error
        return None

    @staticmethod
    def _validate_feed_response(response):
        if response.status_code != 200:
            error_code = (
                FeedError.NOT_FOUND.name
                if response.status_code == 404
                else FeedError.API_ERROR.name
            )
            error_detail = (
                FeedError.NOT_FOUND.value
                if response.status_code == 404
                else FeedError.API_ERROR.value
            )
            raise Exception(f"{error_code}: {error_detail}")

    @staticmethod
    def _validate_dataset(datasets, status_code):
        if status_code != 200 or not datasets:
            error_code = FeedError.NO_DATASET.name
            error_detail = FeedError.NO_DATASET.value
            raise Exception(f"{error_code}: {error_detail}")
        latest_dataset = datasets[0]
        try:
            gtfs_kit.read_feed(latest_dataset["hosted_url"], "km")
        except Exception as e:
            raise Exception(
                f"{FeedError.INVALID_DATASET.name}: {FeedError.INVALID_DATASET.value} -- {e}"
            )

    @staticmethod
    def _create_error_entry(stable_id, error_details, status_code=None):
        if error_details is None:
            return None
        return {
            "stable_id": stable_id,
            "API Endpoint": f"v1/gtfs_feeds/{stable_id}/datasets",
            "API Error Code": status_code,
            "Error Code": error_details.split(": ")[0],
            "Error Details": error_details.split(": ")[1],
        }

    def _log_errors(self, errors):
        table = Table(
            title="Test Errors",
            show_header=True,
            header_style="bold magenta",
            show_lines=True,
            expand=True,
        )
        table.add_column("Stable ID", style="dim")
        table.add_column("Error Code", style="red")
        table.add_column("Error Details", overflow="fold")
        for error in errors:
            table.add_row(
                error["stable_id"], error["Error Code"], error["Error Details"]
            )
        self.console.print(table)
        pandas.DataFrame(errors).to_csv("datasets_validation.csv")
        self.console.log(
            'Datasets validation report saved to "datasets_validation.csv"'
        )
