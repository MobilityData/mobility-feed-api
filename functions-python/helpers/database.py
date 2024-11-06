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

import os
import threading
from typing import Final

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import logging

DB_REUSE_SESSION: Final[str] = "DB_REUSE_SESSION"
lock = threading.Lock()


class Database:
    def __init__(self, database_url: str = None):
        self.database_url = database_url or os.getenv("DATABASE_URL")
        self.echo = True
        self.engine = None
        self.session = None

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
                self.engine = create_engine(database_url, echo=echo)
                self.logger.debug("Database connected.")
            if self.session is not None and self.session.is_active:
                self.session.close()
            self.session = sessionmaker(self.engine)()
            return self.session
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
                logging.info("Database session closed.")
        except Exception as error:
            logging.error(f"Error closing database session: {error}")
            if raise_exception:
                raise error

    def refresh_materialized_view(session, view_name: str) -> bool:
        """
        Refresh Materialized view by name.
        @return: True if the view was refreshed successfully, False otherwise
        """
        try:
            session.execute(
                text(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {view_name}"))
            return True
        except Exception as error:
            logging.error(f"Error raised while refreshing view: {error}")
        return False
