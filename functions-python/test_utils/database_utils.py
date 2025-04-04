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

from typing import Final

from sqlalchemy.orm import Session
from sqlalchemy import text

from shared.database_gen.sqlacodegen_models import Base
from shared.database.database import Database, with_db_session
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


@with_db_session(db_url=default_db_url)
def clean_testing_db(db_session: Session):
    """Deletes all rows from all tables in the test db, excluding those in excluded_tables."""
    try:
        tables_to_delete = [
            table.name
            for table in reversed(Base.metadata.sorted_tables)
            if table.name not in excluded_tables
        ]

        # Delete all rows from each table
        for table_name in tables_to_delete:
            delete_query = f"DELETE FROM {table_name};"
            db_session.execute(text(delete_query))
        db_session.commit()
    except Exception as error:
        print(f"Error while cleaning the test db: {error}")
        logging.error(f"Error while deleting from test db: {error}")


def reset_database_class():
    """Resets the Database class to its initial state."""
    Database.instance = None
    Database.initialized = False
