#
#
#   MobilityData 2025
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#        http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#
# This module provides the PmtilesBuilder class and related functions to generate PMTiles files
# from GTFS datasets. It handles downloading required files from Google Cloud Storage, processing
# and indexing GTFS data, generating GeoJSON and JSON outputs, running Tippecanoe to create PMTiles,
# and uploading the results back to GCS.
import csv
import json
import logging
import os
import pickle
import shutil
import subprocess
from logging import DEBUG, WARNING, INFO, ERROR
from google.cloud import storage

# Files are stored locally to be able to run tippecanoe on them. This is the directory
local_dir = "./workdir"


def build_pmtiles_handler(payload) -> dict:
    """
    Entrypoint for building PMTiles files from a GTFS dataset.
    """
    try:
        feed_stable_id, dataset_stable_id = PmtilesBuilder._get_parameters(payload)
        builder = PmtilesBuilder(
            feed_stable_id=feed_stable_id, dataset_stable_id=dataset_stable_id
        )
        return builder.build_pmtiles()
    except Exception as e:
        return {"error": f"Failed to start PMTiles build: {e}"}


class PmtilesBuilder:
    """
    Orchestrates the end-to-end process of generating PMTiles files from GTFS datasets.

    This class manages downloading required files from Google Cloud Storage, processing and indexing GTFS data,
    generating GeoJSON and JSON outputs, running Tippecanoe to create PMTiles, and uploading results back to GCS.
    Temporary files are stored in the global `workdir` directory for local processing.
    """

    def __init__(
        self,
        feed_stable_id: str | None = None,
        dataset_stable_id: str | None = None,
    ):
        self.bucket = None
        self.feed_stable_id = feed_stable_id
        self.dataset_stable_id = dataset_stable_id
        self.bucket_name = os.getenv("DATASETS_BUCKET_NAME")

    def _log(self, level, msg, *args):
        logger = logging.getLogger()
        if not logger.isEnabledFor(level):
            return
        formatted_msg = msg % args if args else msg
        logger.log(level, "[%s] %s", self.dataset_stable_id, formatted_msg)

    @staticmethod
    def _get_parameters(payload):
        """
        Get parameters from the payload and environment variables.
        """
        feed_stable_id = payload.get("feed_stable_id", None)
        dataset_stable_id = payload.get("dataset_stable_id", None)
        return feed_stable_id, dataset_stable_id

    def build_pmtiles(self) -> dict:
        try:
            if not self.bucket_name:
                return {
                    "error": "DATASETS_BUCKET_NAME environment variable is not defined."
                }
            if not self.feed_stable_id or not self.dataset_stable_id:
                return {
                    "error": "Both feed_stable_id and dataset_stable_id must be defined."
                }
            if self.feed_stable_id not in self.dataset_stable_id:
                return {
                    "error": (
                        "feed_stable_id %s is not a prefix of dataset_stable_id %s."
                        % (self.feed_stable_id, self.dataset_stable_id)
                    )
                }

            self._log(
                INFO, "Starting PMTiles build for dataset %s", self.dataset_stable_id
            )
            unzipped_files_path = (
                f"{self.feed_stable_id}/{self.dataset_stable_id}/extracted"
            )

            self._download_files_from_gcs(unzipped_files_path)

            self._create_shapes_index()

            self._create_routes_geojson()

            self._run_tippecanoe("routes-output.geojson", "routes.pmtiles")

            self._create_stops_geojson()

            self._run_tippecanoe("stops-output.geojson", "stops.pmtiles")

            self._create_routes_json()

            files_to_upload = ["routes.pmtiles", "stops.pmtiles", "routes.json"]
            self._upload_files_to_gcs(files_to_upload)

            # List files in the relevant bucket folder instead of local_dir

            if logging.getLogger().isEnabledFor(DEBUG):
                gcs_prefix = f"{self.feed_stable_id}/{self.dataset_stable_id}/pmtiles/"
                try:  # We don`t want an error here to abort the whole pmtiles operation.
                    blobs = list(self.bucket.list_blobs(prefix=gcs_prefix))
                    file_list = "\n".join(
                        f"{blob.name} ({blob.size} bytes)" for blob in blobs
                    )
                    self._log(DEBUG, "GCS files in %s:\n%s", gcs_prefix, file_list)
                except Exception as e:
                    self._log(
                        ERROR,
                        "Could not list files in bucket %s for path %s: %s",
                        self.bucket_name,
                        gcs_prefix,
                        e,
                    )

            return {
                "message": f"Pmtiles successfully created for dataset {self.dataset_stable_id}."
            }
        except Exception as e:
            logging.exception(
                "Failed to build PMTiles for dataset %s", self.dataset_stable_id
            )
            return {
                "error": f"Failed to build PMTiles for dataset {self.dataset_stable_id}: {e}"
            }

    def _download_files_from_gcs(self, unzipped_files_path):
        self._log(
            INFO,
            "Downloading dataset from GCS bucket %s, directory %s",
            self.bucket_name,
            unzipped_files_path,
        )
        try:
            self._log(DEBUG, "Initializing storage client")
            self.bucket = storage.Client().get_bucket(self.bucket_name)
            self._log(DEBUG, "Getting blobs with prefix: %s", unzipped_files_path)
            blobs = list(self.bucket.list_blobs(prefix=unzipped_files_path))
            self._log(DEBUG, "Found %d blobs", len(blobs))
            if not blobs:
                raise Exception(
                    f"Directory '{unzipped_files_path}' does not exist or is empty in bucket '{self.bucket_name}'."
                )

            if os.path.exists(local_dir):
                shutil.rmtree(local_dir)
            os.makedirs(local_dir, exist_ok=True)
            file_names = [
                "routes.txt",
                "shapes.txt",
                "stop_times.txt",
                "trips.txt",
                "stops.txt",
            ]
            for file_name in file_names:
                blob_path = f"{unzipped_files_path}/{file_name}"
                blob = self.bucket.blob(blob_path)
                local_path = os.path.join(local_dir, file_name)
                blob.download_to_filename(local_path)
                self._log(DEBUG, "Downloaded %s to %s", blob_path, local_path)
            return
        except Exception as e:
            raise Exception(f"Failed to download files from GCS: {e}") from e

    def _upload_files_to_gcs(self, file_to_upload):
        dest_prefix = f"{self.feed_stable_id}/{self.dataset_stable_id}/pmtiles"
        self._log(
            INFO,
            "Uploading files to GCS bucket %s, directory %s",
            self.bucket_name,
            dest_prefix,
        )
        try:
            blobs_to_delete = list(self.bucket.list_blobs(prefix=dest_prefix + "/"))
            for blob in blobs_to_delete:
                blob.delete()
                self._log(DEBUG, "Deleted existing blob: %s", blob.name)
            for file_name in file_to_upload:
                file_path = os.path.join(local_dir, file_name)
                if not os.path.exists(file_path):
                    self._log(WARNING, "File not found: %s", file_path)
                    continue
                blob_path = f"{dest_prefix}/{file_name}"
                blob = self.bucket.blob(blob_path)
                blob.upload_from_filename(file_path)
                self._log(
                    DEBUG,
                    "Uploaded %s to gs://%s/%s",
                    file_path,
                    self.bucket_name,
                    blob_path,
                )
        except Exception as e:
            raise Exception(f"Failed to upload files to GCS: {e}") from e

    def _create_shapes_index(self):
        self._log(INFO, "Creating shapes index")
        try:
            index = {}
            shapes = f"{local_dir}/shapes.txt"
            outfile = f"{local_dir}/shapes_index.pkl"
            with open(shapes, "r", encoding="utf-8") as f:
                header = f.readline()
                columns = next(csv.reader([header]))
                count = 0
                while True:
                    pos = f.tell()
                    line = f.readline()
                    if not line:
                        break
                    row = dict(zip(columns, next(csv.reader([line]))))
                    sid = row["shape_id"]
                    index.setdefault(sid, []).append(pos)
                    count += 1
                    if count % 1000000 == 0:
                        self._log(DEBUG, "Indexed %d lines so far...", count)
            self._log(DEBUG, "Total indexed lines: %d", count)
            self._log(DEBUG, "Total unique shape_ids: %d", len(index))
            with open(outfile, "wb") as idxf:
                pickle.dump(index, idxf)
        except Exception as e:
            raise Exception(f"Failed to create shapes index: {e}") from e

    def _read_csv(self, filename):
        try:
            self._log(DEBUG, "Loading %s", filename)
            with open(filename, newline="", encoding="utf-8") as f:
                return list(csv.DictReader(f))
        except Exception as e:
            raise Exception(f"Failed to read CSV file {filename}: {e}") from e

    def _get_shape_points(self, shape_id, index):
        self._log(DEBUG, "Getting shape points for shape_id %s", shape_id)
        try:
            points = []
            shapes_file = f"{local_dir}/shapes.txt"
            with open(shapes_file, "r", encoding="utf-8") as f:
                for pos in index.get(shape_id, []):
                    f.seek(pos)
                    line = f.readline()
                    row = dict(zip(index["columns"], next(csv.reader([line]))))
                    points.append(
                        (
                            float(row["shape_pt_lon"]),
                            float(row["shape_pt_lat"]),
                            int(row["shape_pt_sequence"]),
                        )
                    )
            points.sort(key=lambda x: x[2])
            self._log(DEBUG, "  Found %d points for shape_id %s", len(points), shape_id)
            return [pt[:2] for pt in points]
        except Exception as e:
            raise Exception(f"Failed to get shape points for {shape_id}: {e}") from e

    def _create_routes_geojson(self):
        self._log(INFO, "Creating routes geojson")
        try:
            self._log(DEBUG, "Loading shapes_index.pkl...")
            shapes_index_file = f"{local_dir}/shapes_index.pkl"
            shapes_file = f"{local_dir}/shapes.txt"
            trips_file = f"{local_dir}/trips.txt"
            routes_file = f"{local_dir}/routes.txt"
            stops_file = f"{local_dir}/stops.txt"
            stop_times_file = f"{local_dir}/stop_times.txt"
            with open(shapes_index_file, "rb") as idxf:
                shapes_index = pickle.load(idxf)
            self._log(DEBUG, "Loaded index for %d shape_ids.", len(shapes_index))

            with open(shapes_file, "r", encoding="utf-8") as f:
                header = f.readline()
                shapes_columns = next(csv.reader([header]))
            shapes_index["columns"] = shapes_columns

            routes = {r["route_id"]: r for r in self._read_csv(routes_file)}
            self._log(DEBUG, "Loaded %d routes.", len(routes))

            trips = list(self._read_csv(trips_file))
            self._log(DEBUG, "Loaded %d trips.", len(trips))

            stops = {
                s["stop_id"]: (float(s["stop_lon"]), float(s["stop_lat"]))
                for s in self._read_csv(stops_file)
            }
            self._log(DEBUG, "Loaded %d stops.", len(stops))

            stop_times_by_trip = {}
            self._log(
                DEBUG,
                "Grouping stop_times by trip_id for dataset %s",
                self.dataset_stable_id,
            )
            with open(stop_times_file, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    stop_times_by_trip.setdefault(row["trip_id"], []).append(row)
            self._log(
                DEBUG, "Grouped stop_times for %d trips.", len(stop_times_by_trip)
            )

            features = []
            for i, (route_id, route) in enumerate(routes.items(), 1):
                if i % 100 == 0 or i == 1:
                    self._log(
                        DEBUG,
                        "Processing route %d/%d (route_id: %s)",
                        i,
                        len(routes),
                        route_id,
                    )
                trip = next((t for t in trips if t["route_id"] == route_id), None)
                if not trip:
                    self._log(
                        INFO, "  No trip found for route_id %s, skipping.", route_id
                    )
                    continue
                coordinates = []
                if "shape_id" in trip and trip["shape_id"]:
                    self._log(
                        DEBUG,
                        "  Using shape_id %s for route_id %s",
                        trip["shape_id"],
                        route_id,
                    )
                    coordinates = self._get_shape_points(trip["shape_id"], shapes_index)
                    if isinstance(coordinates, dict) and "error" in coordinates:
                        raise Exception(
                            f"Error getting shape points for shape_id {trip['shape_id']}: {coordinates['error']}"
                        )
                if not coordinates:
                    trip_stop_times = stop_times_by_trip.get(trip["trip_id"], [])
                    trip_stop_times.sort(key=lambda x: int(x["stop_sequence"]))
                    coordinates = [
                        stops[st["stop_id"]]
                        for st in trip_stop_times
                        if st["stop_id"] in stops
                    ]
                    self._log(
                        DEBUG,
                        "  Used %d stop coordinates for route_id %s",
                        len(coordinates),
                        route_id,
                    )
                if not coordinates:
                    self._log(
                        INFO,
                        "  No coordinates found for route_id %s, skipping.",
                        route_id,
                    )
                    continue
                features.append(
                    {
                        "type": "Feature",
                        "properties": {k: route[k] for k in route},
                        "geometry": {"type": "LineString", "coordinates": coordinates},
                    }
                )

            self._log(
                DEBUG, "Writing %d features to routes-output.geojson...", len(features)
            )
            routes_geojson = f"{local_dir}/routes-output.geojson"
            with open(routes_geojson, "w", encoding="utf-8") as f:
                json.dump({"type": "FeatureCollection", "features": features}, f)
        except Exception as e:
            raise Exception(f"Failed to create routes GeoJSON: {e}") from e

    def _run_tippecanoe(self, input_file, output_file):
        self._log(INFO, "Running tippecanoe for input file %s", input_file)
        try:
            cmd = [
                "tippecanoe",
                "-o",
                f"{local_dir}/{output_file}",
                "--force",
                "--no-tile-size-limit",
                "-zg",
                f"{local_dir}/{input_file}",
            ]
            self._log(DEBUG, "Running command: %s", " ".join(cmd))
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.stdout:
                self._log(DEBUG, "Tippecanoe output:\n%s", result.stdout)
            if result.returncode != 0:
                self._log(ERROR, "Tippecanoe error:\n%s", result.stderr)
                raise Exception(f"Tippecanoe failed with exit code {result.returncode}")
            self._log(DEBUG, "Tippecanoe command executed successfully.")
        except Exception as e:
            raise Exception(
                f"Failed to run tippecanoe for output file {output_file}: {e}"
            ) from e

    def _create_stops_geojson(self):
        self._log(INFO, "Creating stops geojson...")
        try:
            stops = self._read_csv(f"{local_dir}/stops.txt")
            if isinstance(stops, dict) and "error" in stops:
                return stops
            self._log(DEBUG, "Loaded %d stops.", len(stops))

            features = []
            for i, stop in enumerate(stops, 1):
                try:
                    lon = float(stop["stop_lon"])
                    lat = float(stop["stop_lat"])
                except (KeyError, ValueError):
                    self._log(
                        INFO,
                        "Skipping stop %s: invalid coordinates",
                        stop.get("stop_id", ""),
                    )
                    continue
                features.append(
                    {
                        "type": "Feature",
                        "properties": {k: stop[k] for k in stop},
                        "geometry": {"type": "Point", "coordinates": [lon, lat]},
                    }
                )

            geojson = {"type": "FeatureCollection", "features": features}
            stops_geojson = f"{local_dir}/stops-output.geojson"

            self._log(
                DEBUG,
                "Writing %d features to stops-output.geojson for dataset %s",
                len(features),
                self.dataset_stable_id,
            )
            with open(stops_geojson, "w", encoding="utf-8") as f:
                json.dump(geojson, f)
        except Exception as e:
            raise Exception(
                f"Failed to create stops GeoJSON for dataset {self.dataset_stable_id}: {e}"
            ) from e

    def _create_routes_json(self):
        self._log(INFO, "Creating routes json...")
        try:
            routes = []
            with open(f"{local_dir}/routes.txt", newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    route = {
                        "routeId": row.get("route_id", ""),
                        "routeName": row.get("route_long_name", ""),
                        "color": f"#{row.get('route_color', '000000')}",
                        "textColor": f"#{row.get('route_text_color', 'FFFFFF')}",
                        "routeType": f"{row.get('route_type', '3')}",
                    }
                    routes.append(route)

            with open(f"{local_dir}/routes.json", "w", encoding="utf-8") as f:
                json.dump(routes, f, ensure_ascii=False, indent=4)

            self._log(DEBUG, "Converted %d routes to routes.json.", len(routes))
        except Exception as e:
            raise Exception(f"Failed to create routes JSON for dataset: {e}") from e
