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
from typing import Final

from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
from sqlalchemy import text

from database_gen.sqlacodegen_models import Base
from helpers.database import Database
import logging

logging.basicConfig()
logging.getLogger("sqlalchemy").setLevel(logging.ERROR)

default_db_url: Final[
    str
] = "postgresql://postgres:postgres@localhost:54320/MobilityDatabaseTest"

excluded_tables: Final[list[str]] = [
    "databasechangelog",
    "databasechangeloglock",
    "geography_columns",
    "geometry_columns",
    "spatial_ref_sys",
    # Excluding the views
    "feedsearch",
    "location_with_translations_en",
]


def get_testing_engine() -> Engine:
    """Returns a SQLAlchemy engine for the test db."""
    db = Database(database_url=default_db_url, echo=False)
    return db.engine


def get_testing_session() -> Session:
    """Returns a SQLAlchemy session for the test db."""
    engine = get_testing_engine()
    return Session(bind=engine)


def clean_testing_db():
    """Deletes all rows from all tables in the test db, excluding those in excluded_tables."""
    engine = get_testing_engine()
    with contextlib.closing(engine.connect()) as con:
        trans = con.begin()
        try:
            tables_to_delete = [
                table.name
                for table in reversed(Base.metadata.sorted_tables)
                if table.name not in excluded_tables
            ]
            # Disable triggers for each table
            for table_name in tables_to_delete:
                con.execute(text(f"ALTER TABLE {table_name} DISABLE TRIGGER ALL;"))

            # Delete all rows from each table
            for table_name in tables_to_delete:
                delete_query = f"DELETE FROM {table_name};"
                con.execute(text(delete_query))

            # Re-enable triggers for each table
            for table_name in tables_to_delete:
                con.execute(text(f"ALTER TABLE {table_name} ENABLE TRIGGER ALL;"))

            trans.commit()
        except Exception as error:
            trans.rollback()
            logging.error(f"Error while deleting from test db: {error}")
