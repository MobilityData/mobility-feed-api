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

from contextlib import contextmanager
import os
import threading
from typing import Final, Optional, TYPE_CHECKING

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import logging

if TYPE_CHECKING:
    from sqlalchemy.engine import Engine

DB_REUSE_SESSION: Final[str] = "DB_REUSE_SESSION"


def with_db_session(func):
    """
    Decorator to handle the session management
    :param func: the function to decorate
    :return: the decorated function
    """

    def wrapper(*args, **kwargs):
        db_session = kwargs.get("db_session")
        if db_session is None:
            db = Database()
            with db.start_db_session() as session:
                kwargs["db_session"] = session
                return func(*args, **kwargs)
        return func(*args, **kwargs)

    return wrapper


class Database:
    instance = None
    initialized = False
    lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if not isinstance(cls.instance, cls):
            with lock:
                if not isinstance(cls.instance, cls):
                    cls.instance = object.__new__(cls)
        return cls.instance

    def __init__(self, database_url: Optional[str] = None, echo: bool = True):
        with Database.lock:
            if Database.initialized:
                return

            Database.initialized = True
            self.database_url: str = (
                database_url if database_url else os.getenv("FEEDS_DATABASE_URL")
            )
            if self.database_url is None:
                raise Exception("Database URL not provided.")

            self.echo = echo
            self.engine = create_engine(
                self.database_url, echo=self.echo, pool_size=5, max_overflow=0
            )
            self.connection_attempts: int = 0
            self.Session = sessionmaker(bind=self.engine, autoflush=False)
            self.logger = logging.getLogger(__name__)

    @contextmanager
    def start_db_session(self):
        session = self.Session()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def is_session_reusable():
        return os.getenv("%s" % DB_REUSE_SESSION, "false").lower() == "true"

    def refresh_materialized_view(self, session, view_name: str) -> bool:
        """
        Refresh Materialized view by name.
        @return: True if the view was refreshed successfully, False otherwise
        """
        try:
            session.execute(text(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {view_name}"))
            return True
        except Exception as error:
            self.logger.error(f"Error raised while refreshing view: {error}")
            return False
