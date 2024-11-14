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
    from sqlalchemy.orm import Session

DB_REUSE_SESSION: Final[str] = "DB_REUSE_SESSION"
lock = threading.Lock()


class Database:
    def __init__(self, database_url: Optional[str] = None, echo: bool = True):
        self.database_url: str = database_url if database_url else os.getenv(
            "FEEDS_DATABASE_URL")
        if self.database_url is None:
            raise Exception("Database URL not provided.")

        self.echo = echo
        self.engine: "Engine" = None
        self.connection_attempts: int = 0
        self.logger = logging.getLogger(__name__)

    def get_engine(self) -> "Engine":
        """
        Returns the database engine
        """
        if self.engine is None:
            global lock
            with lock:
                self.engine = create_engine(
                    self.database_url, echo=self.echo, pool_size=5, max_overflow=0)
                self.logger.debug("Database connected.")

        return self.engine

    @contextmanager
    def start_db_session(self):
        """
        Starts a session
        :return: True if the session was started, False otherwise
        """
        global lock
        try:
            lock.acquire()
            if self.engine is None:
                self.connection_attempts += 1
                self.logger.debug(
                    f"Database connection attempt #{self.connection_attempts}.")
                self.engine = create_engine(
                    self.database_url, echo=self.echo, pool_size=5, max_overflow=0)
                self.logger.debug("Database connected.")
            # if self.session is not None and self.session.is_active:
            #     self.session.close()
            session = sessionmaker(self.engine)()
            yield session
        except Exception as e:
            self.logger.error(
                f"Database new session creation failed with exception: \n {e}")
        finally:
            lock.release()

    def is_session_reusable():
        return os.getenv("%s" % DB_REUSE_SESSION, "false").lower() == "true"

    def close_db_session(self, raise_exception: bool = True):
        """
        Closes the database session
        """
        try:
            if self.session is not None:
                self.session.close()
                self.logger.info("Database session closed.")
        except Exception as error:
            self.logger.error(f"Error closing database session: {error}")
            if raise_exception:
                raise error

    def refresh_materialized_view(self, view_name: str) -> bool:
        """
        Refresh Materialized view by name.
        @return: True if the view was refreshed successfully, False otherwise
        """
        try:
            self.session.execute(
                text(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {view_name}"))
            return True
        except Exception as error:
            self.logger.error(f"Error raised while refreshing view: {error}")
        return False
