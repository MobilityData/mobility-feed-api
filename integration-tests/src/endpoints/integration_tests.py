import platform
import time
from enum import Enum

import pandas
import requests
from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    TimeElapsedColumn,
)
from rich.table import Table

from api.src.utils.data_utils import set_up_defaults


class DatasetValidationWarning(Enum):
    NOT_FOUND = "Feed not returned from the API"
    API_ERROR = "API returned an error code"
    NO_DATASET = "No dataset found for feed"


class IntegrationTests:
    def __init__(self, file_path, access_token, url, progress=None, console=None):
        feeds = pandas.read_csv(file_path)
        feeds = set_up_defaults(feeds)
        self.file_path = file_path
        self.gtfs_feeds = feeds[(feeds.data_type == "gtfs")]
        self.gtfs_rt_feeds = feeds[(feeds.data_type == "gtfs_rt")]
        self.access_token = access_token
        self.base_url = url
        self.console = console if console else Console(record=True)
        self.progress = progress

    def _test_filter_by_country_code(
        self, country_code, endpoint, validate_location=False, task_id=None, index="1/1"
    ):
        """Helper function for filtering the response by country code."""
        country_code = country_code.strip()
        response = self.get_response(endpoint, params={"country_code": country_code})
        assert response.status_code == 200, (
            f"Expected 200 status code for country code filter '{country_code}', got "
            f"{response.status_code}."
        )
        feeds = response.json()
        assert (
            len(feeds) > 0
        ), f"Expected at least one feed with country code '{country_code}', got 0."
        if validate_location:
            for feed in feeds:
                country_codes = [
                    location["country_code"] for location in feed["locations"]
                ]
                assert country_code in country_codes, (
                    f"Expected all feeds to have country code '{country_code}', but found country codes "
                    f"'{country_codes}'"
                )
        self._update_progression(
            task_id, f"Validated country code {country_code}", index
        )

    def _update_progression(self, task_id, validation_description, index):
        """Helper function for updating the progression of a task."""
        if self.progress is not None and task_id is not None:
            self.progress.update(
                task_id, advance=1, description=f"{validation_description} ({index})"
            )

    @staticmethod
    def _sample_country_codes(df, n):
        """Helper function for sampling random unique country codes."""
        filtered_country_codes = df["location.country_code"].dropna()
        filtered_country_codes = filtered_country_codes[filtered_country_codes != ""]
        filtered_country_codes = filtered_country_codes[
            ~filtered_country_codes.str.isnumeric()
        ]

        unique_country_codes = filtered_country_codes.unique()

        # Sample min(n, len(unique values)) country codes
        num_samples = min(len(unique_country_codes), n)
        return pandas.Series(unique_country_codes).sample(n=num_samples, random_state=1)

    def _test_filter_by_provider(self, provider, endpoint, task_id, index):
        """Helper function for filtering the response by provider."""
        response = self.get_response(endpoint, params={"provider": provider})
        assert response.status_code == 200, (
            f"Expected 200 status code for provider filter '{provider}', got "
            f"{response.status_code}."
        )
        feeds = response.json()
        assert (
            len(feeds) > 0
        ), f"Expected at least one feed with provider '{provider}', got 0."
        for feed in feeds:
            assert (
                provider.lower() in feed.get("provider").lower()
            ), f"Expected all feeds to be provided by '{provider}', but found '{feed.get('provider')}'"
        self._update_progression(task_id, f"Validated provider {provider}", index)

    def _test_filter_by_municipality(
        self, municipality, endpoint, validate_location=False, task_id=None, index="1/1"
    ):
        """Helper function for filtering the response by municipality."""
        municipality = municipality.strip()
        response = self.get_response(endpoint, params={"municipality": municipality})
        assert response.status_code == 200, (
            f"Expected 200 status code for municipality filter '{municipality}', got "
            f"{response.status_code}."
        )
        feeds = response.json()
        assert (
            len(feeds) > 0
        ), f"Expected at least one feed with municipality '{municipality}', got 0."

        lowercase_municipality = municipality.lower()
        if validate_location:
            for feed in feeds:
                municipalities = [
                    location["municipality"] for location in feed["locations"]
                ]
                is_municipality_valid = [
                    lowercase_municipality in m.lower() for m in municipalities
                ]
                assert any(is_municipality_valid), (
                    f"Expected all feeds to have municipality '{municipality}', but found municipalities "
                    f"'{municipalities}'"
                )
        self._update_progression(
            task_id, f"Validated municipality {municipality}", index
        )

    @staticmethod
    def _sample_municipalities(df, n):
        """Helper function for sampling random unique country codes."""
        unique_country_codes = df["location.municipality"].unique()

        # Sample min(n, len(unique values)) municipalities
        num_samples = min(len(unique_country_codes), n)
        return pandas.Series(unique_country_codes).sample(n=num_samples, random_state=1)

    def get_response(self, url_suffix, params=None, timeout=15):
        """Helper function to get response from the API."""
        url = self.base_url + "/" + url_suffix
        headers = {
            "Authorization": "Bearer " + self.access_token,
            "User-Agent": f"MobilityData Feed API Integration Tests (Python {platform.python_version()})",
        }
        return requests.get(url, params=params, headers=headers, timeout=timeout)

    @staticmethod
    def get_test_methods_for_class(cls):
        """Utility method to get test methods for a given class."""
        return [
            method_name
            for method_name in dir(cls)
            if callable(getattr(cls, method_name))
            and method_name.startswith("test_")
            and method_name != "test_all"
        ]

    def test_all(self, target_classes=[], excluded_classes=[]):
        """Test all endpoints."""
        console = self.console
        console.clear()

        passed_tests = []
        failed_tests = []
        skipped_tests = []

        # Descriptive panel message
        description = """
        [bold]Integration Tests for Mobility Feeds API[/bold]

        This suite of tests is designed to validate the functionality and reliability of the Mobility Feeds API. It
        covers a range of scenarios including:

        - Filtering feeds by country code, provider, and municipality to ensure accurate data retrieval.
        - Verifying the API's response codes, content types, and payload structures.

        """

        # Print the panel with the descriptive message
        console.print(
            Panel(
                description,
                title="[bold green]API Integration Test Suite[/bold green]",
                subtitle="Test Execution In Progress",
            )
        )

        # Dynamically find all child classes and their test methods
        child_classes = IntegrationTests.__subclasses__()
        test_methods = [
            (child, self.get_test_methods_for_class(child))
            for child in child_classes
            if (child.__name__ in target_classes if len(target_classes) > 0 else True)
            and (
                child.__name__ not in excluded_classes
                if len(excluded_classes) > 0
                else True
            )
        ]

        n_tests = sum(len(methods) for _, methods in test_methods)

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
            console=console,
            transient=True,
        ) as progress:
            test_task = progress.add_task("[cyan]Running tests...", total=n_tests)

            for child_class, methods in test_methods:
                try:
                    instance = child_class(
                        self.file_path,
                        self.access_token,
                        self.base_url,
                        progress,
                        self.console,
                    )
                except TypeError:
                    instance = child_class(
                        self.file_path, self.access_token, self.base_url, progress
                    )

                for method_name in methods:
                    method = getattr(instance, method_name)
                    method_display = f"{child_class.__name__}.{method_name}"
                    try:
                        start_time = time.time()
                        method()
                        self.clear_tasks(test_task, progress)
                        progress.log(
                            f"{method_display} [green]PASSED :white_check_mark: [/green] in [yellow]"
                            f"{(time.time() - start_time):.2f}s[/yellow]"
                        )
                        passed_tests.append(method_display)
                    except AssertionError:
                        progress.log(
                            f"{method_display} [red]FAILED :cross_mark: [/red] in [yellow]"
                            f"{(time.time() - start_time):.2f}s[/yellow]"
                        )
                        progress.console.print_exception(
                            show_locals=True,
                            suppress=["endpoints/integration_tests.py"],
                            max_frames=0,
                        )
                        failed_tests.append(method_display)
                    except Exception:
                        progress.log(
                            f"{method_display} [yellow]SKIPPED :warning: [/yellow] in [yellow]"
                            f"{(time.time() - start_time):.2f}s[/yellow]"
                        )
                        progress.console.print_exception(
                            show_locals=True,
                            suppress=["endpoints/integration_tests.py"],
                            max_frames=0,
                        )
                        skipped_tests.append(method_display)
                    finally:
                        progress.update(test_task, advance=1)

        # Print the test report
        table = Table(
            title="[bold cyan]TEST REPORT[/bold cyan]", show_lines=True, expand=True
        )

        table.add_column("Status", justify="center", vertical="middle")
        table.add_column(
            "Nb Of Tests", style="yellow", justify="center", vertical="middle"
        )
        table.add_column(
            "Tests List", justify="left", overflow="fold", vertical="middle"
        )

        table.add_row(
            "[green]PASSED[/green]", f"{len(passed_tests)}", ", ".join(passed_tests)
        )
        table.add_row(
            "[red]FAILED[/red]", f"{len(failed_tests)}", ", ".join(failed_tests)
        )
        table.add_row(
            "[yellow]SKIPPED[/yellow]",
            f"{len(skipped_tests)}",
            ", ".join(skipped_tests),
        )

        console.log(table)
        console.save_html("integration_tests_log.html")
        console.log('Test report saved to "integration_tests_log.html"')
        if len(failed_tests) or len(skipped_tests):
            raise AssertionError("Some tests failed or were skipped.")

    @staticmethod
    def clear_tasks(test_task, progress):
        for task in progress.task_ids:
            if task != test_task:
                progress.remove_task(task)
