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

import contextlib
import os
from typing import Final

from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from database_gen.sqlacodegen_models import Base
from helpers.database import get_db_engine
import logging

logging.basicConfig()
logging.getLogger('sqlalchemy').setLevel(logging.ERROR)

default_db_url: Final[str] = "postgresql://postgres:postgres@localhost:54320/MobilityDatabaseTest"

excluded_tables: Final[list[str]] = [
    "databasechangelog",
    "databasechangeloglock",
    "geography_columns",
    "geometry_columns",
    "spatial_ref_sys",
]


def get_testing_engine() -> Engine:
    """Returns a SQLAlchemy engine for the test db."""
    return get_db_engine(os.getenv("TEST_FEEDS_DATABASE_URL", default=default_db_url), echo=False)


def get_testing_session() -> Session:
    """Returns a SQLAlchemy session for the test db."""
    engine = get_testing_engine()
    return Session(bind=engine)


def clean_testing_db():
    """Truncates all table in the test db."""
    engine = get_testing_engine()
    with contextlib.closing(engine.connect()) as con:
        trans = con.begin()
        query = 'TRUNCATE {} RESTART IDENTITY;'.format(
            ','.join(table.name
                     for table in filter(lambda t: t.name not in excluded_tables, Base.metadata.sorted_tables)))
        con.execute(query)
        trans.commit()

