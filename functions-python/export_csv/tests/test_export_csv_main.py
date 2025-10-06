#
#   MobilityData 2023
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
import io
import unittest

import pandas as pd
import pandas.testing as pdt
import main

# This CSV has been created by running the tests once to extract the resulting csv, then examine the CSV to make sure
# the data is correct.
expected_csv = """
id,data_type,entity_type,location.country_code,location.subdivision_name,location.municipality,provider,is_official,name,note,feed_contact_email,static_reference,urls.direct_download,urls.authentication_type,urls.authentication_info,urls.api_key_parameter_name,urls.latest,urls.license,location.bounding_box.minimum_latitude,location.bounding_box.maximum_latitude,location.bounding_box.minimum_longitude,location.bounding_box.maximum_longitude,location.bounding_box.extracted_on,status,features,redirect.id,redirect.comment
gtfs-0,gtfs,,CA,Quebec,Laval,gtfs-0 Some fake company,True,gtfs-0 Some fake name,gtfs-0 Some fake note,gtfs-0_some_fake_email@fake.com,,https://gtfs-0_some_fake_producer_url,0,,,https://url_prefix/gtfs-0/latest.zip,https://gtfs-0_some_fake_license_url,-9.0,9.0,-18.0,18.0,2025-01-12 00:00:00+00:00,active,Route Colors|Shapes,,
gtfs-1,gtfs,,CA,Quebec,Montreal,gtfs-1 Some fake company,True,gtfs-1 Some fake name,gtfs-1 Some fake note,gtfs-1_some_fake_email@fake.com,,https://gtfs-1_some_fake_producer_url,0,,,https://url_prefix/gtfs-1/latest.zip,https://gtfs-1_some_fake_license_url,-9.0,9.0,-18.0,18.0,2025-01-12 00:00:00+00:00,active,Route Colors|Shapes,,
gtfs-2,gtfs,,,,,gtfs-2 Some fake company,True,gtfs-2 Some fake name,gtfs-2 Some fake note,gtfs-2_some_fake_email@fake.com,,https://gtfs-2_some_fake_producer_url,0,,,,https://gtfs-2_some_fake_license_url,,,,,,inactive,,gtfs-0,Some redirect comment
gtfs-deprecated-0,gtfs,,,,,gtfs-deprecated-0 Some fake company,True,gtfs-deprecated-0 Some fake name,gtfs-deprecated-0 Some fake note,gtfs-deprecated-0_some_fake_email@fake.com,,https://gtfs-deprecated-0_some_fake_producer_url,0,,,,https://gtfs-0_some_fake_license_url,,,,,,deprecated,,,
gtfs-deprecated-1,gtfs,,,,,gtfs-deprecated-1 Some fake company,True,gtfs-deprecated-1 Some fake name,gtfs-deprecated-1 Some fake note,gtfs-deprecated-1_some_fake_email@fake.com,,https://gtfs-deprecated-1_some_fake_producer_url,1,,,,https://gtfs-1_some_fake_license_url,,,,,,deprecated,,,
gtfs-rt-0,gtfs_rt,tu|vp,,,,gtfs-rt-0 Some fake company,True,gtfs-rt-0 Some fake name,gtfs-rt-0 Some fake note,gtfs-rt-0_some_fake_email@fake.com,gtfs-0,https://gtfs-rt-0_some_fake_producer_url,0,https://gtfs-rt-0_some_fake_authentication_info_url,gtfs-rt-0_fake_api_key_parameter_name,,https://gtfs-rt-0_some_fake_license_url,-9.0,9.0,-18.0,18.0,2025-01-12 00:00:00+00:00,active,,,
gtfs-rt-1,gtfs_rt,vp,,,,gtfs-rt-1 Some fake company,True,gtfs-rt-1 Some fake name,gtfs-rt-1 Some fake note,gtfs-rt-1_some_fake_email@fake.com,,https://gtfs-rt-1_some_fake_producer_url,1,https://gtfs-rt-1_some_fake_authentication_info_url,gtfs-rt-1_fake_api_key_parameter_name,,https://gtfs-rt-1_some_fake_license_url,,,,,,inactive,,gtfs-rt-0|gtfs-rt-2,comment 1|comment 2
gtfs-rt-2,gtfs_rt,vp,,,,gtfs-rt-2 Some fake company,True,gtfs-rt-2 Some fake name,gtfs-rt-2 Some fake note,gtfs-rt-2_some_fake_email@fake.com,,https://gtfs-rt-2_some_fake_producer_url,2,https://gtfs-rt-2_some_fake_authentication_info_url,gtfs-rt-2_fake_api_key_parameter_name,,https://gtfs-rt-2_some_fake_license_url,,,,,,active,,,
"""  # noqa


class TestExportCSV(unittest.TestCase):
    def test_export_csv(self):
        csv_file_path = "./output.csv"
        main.export_csv(csv_file_path)
        df_actual = pd.read_csv(csv_file_path)
        print(f"Collected data for {len(df_actual)} feeds.")

        df_expected = pd.read_csv(io.StringIO(expected_csv))

        pdt.assert_frame_equal(df_actual, df_expected)
        print("DataFrames are equal.")
