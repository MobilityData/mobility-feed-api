#
#   MobilityData 2025
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

from datetime import datetime, timedelta
from uuid import uuid4

import pytest

from shared.database.database import with_db_session
from shared.database_gen.sqlacodegen_models import (
    Gtfsdataset,
    Gtfsfeed,
)
from test_shared.test_utils.database_utils import (
    clean_testing_db,
    default_db_url,
)

future_date = datetime.now() + timedelta(days=15)
past_date = datetime.now() - timedelta(days=15)


def make_dataset(feed_id: str, start: datetime, end: datetime) -> Gtfsdataset:
    return Gtfsdataset(
        id=str(uuid4()),
        feed_id=feed_id,
        service_date_range_start=start,
        service_date_range_end=end,
    )


@with_db_session(db_url=default_db_url)
def populate_database(db_session):
    id_range_by_status = {
        "inactive": (0, 6),
        "active": (7, 10),
        "deprecated": (11, 15),
        "development": (16, 17),
        "future": (18, 29),
    }
    feeds = {}
    for status, (a, b) in id_range_by_status.items():
        for _id in map(str, range(a, b + 1)):
            feed = Gtfsfeed(id=str(_id), status=status, stable_id="mdb-" + str(_id))
            db_session.add(feed)
            feeds[_id] = feed
    db_session.flush()
    # -> inactive
    for _id in [
        "0",  # already inactive
        "7",
        "8",
        "22",
    ]:
        dataset = make_dataset(_id, past_date, past_date)
        db_session.add(dataset)
        db_session.flush()
        feeds[_id].latest_dataset_id = dataset.id

    # -> active
    for _id in [
        "2",
        "9",  # already active
        "12",  # deprecated
        "16",  # development
        "25",
    ]:
        dataset = make_dataset(_id, past_date, future_date)
        db_session.add(dataset)
        db_session.flush()
        feeds[_id].latest_dataset_id = dataset.id

    # -> future
    for _id in [
        "10",
    ]:
        dataset1 = make_dataset(_id, past_date, future_date)
        db_session.add(dataset1)
        dataset2 = make_dataset(_id, future_date, future_date)
        db_session.add(dataset2)
        db_session.flush()
        feeds[_id].latest_dataset_id = dataset2.id

    db_session.commit()


@pytest.fixture(autouse=True)
def setup():
    clean_testing_db()
    populate_database()
