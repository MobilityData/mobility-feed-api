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
from shared.database_gen.sqlacodegen_models import (
    Feed,
    Gtfsdataset,
)
from test_shared.test_utils.database_utils import (
    clean_testing_db,
    get_testing_session,
)

future_date = datetime.now() + timedelta(days=15)
past_date = datetime.now() - timedelta(days=15)


def make_dataset(
    feed_id: str, latest: bool, start: datetime, end: datetime
) -> Gtfsdataset:
    return Gtfsdataset(
        id=str(uuid4()),
        feed_id=feed_id,
        latest=latest,
        service_date_range_start=start,
        service_date_range_end=end,
    )


def populate_database():
    session = get_testing_session()

    id_range_by_status = {
        "inactive": (0, 6),
        "active": (7, 10),
        "deprecated": (11, 15),
        "development": (16, 17),
        "future": (18, 29),
    }
    for status, (a, b) in id_range_by_status.items():
        for _id in map(str, range(a, b + 1)):
            session.add(Feed(id=str(_id), status=status))

    # -> inactive
    for _id in [
        "0",  # already inactive
        "7",
        "8",
        "22",
    ]:
        session.add(make_dataset(_id, True, past_date, past_date))

    # -> active
    for _id in [
        "2",
        "9",  # already active
        "12",  # deprecated
        "16",  # development
        "25",
    ]:
        session.add(make_dataset(_id, True, past_date, future_date))

    # -> future
    for _id in [
        "10",
    ]:
        session.add(make_dataset(_id, False, past_date, past_date))
        session.add(make_dataset(_id, True, future_date, future_date))

    session.commit()


def pytest_sessionstart(session):
    clean_testing_db()
    populate_database()
