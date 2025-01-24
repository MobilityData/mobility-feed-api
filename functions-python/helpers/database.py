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
import logging
import os
import threading
from typing import Optional

from sqlalchemy import create_engine, text, event, Engine
from sqlalchemy.orm import sessionmaker, Session, mapper, class_mapper

from shared.database_gen.sqlacodegen_models import (
    Feed,
    Gtfsfeed,
    Gtfsrealtimefeed,
    Gbfsfeed,
)

LOGGER = logging.getLogger(__name__)


def configure_polymorphic_mappers():
    """
    Configure the polymorphic mappers allowing polymorphic values on relationships.
    """
    feed_mapper = class_mapper(Feed)
    # Configure the polymorphic mapper using date_type as discriminator for the Feed class
    feed_mapper.polymorphic_on = Feed.data_type
    feed_mapper.polymorphic_identity = Feed.__tablename__.lower()

    gtfsfeed_mapper = class_mapper(Gtfsfeed)
    gtfsfeed_mapper.inherits = feed_mapper
    gtfsfeed_mapper.polymorphic_identity = Gtfsfeed.__tablename__.lower()

    gtfsrealtimefeed_mapper = class_mapper(Gtfsrealtimefeed)
    gtfsrealtimefeed_mapper.inherits = feed_mapper
    gtfsrealtimefeed_mapper.polymorphic_identity = (
        Gtfsrealtimefeed.__tablename__.lower()
    )

    gbfsfeed_mapper = class_mapper(Gbfsfeed)
    gbfsfeed_mapper.inherits = feed_mapper
    gbfsfeed_mapper.polymorphic_identity = Gbfsfeed.__tablename__.lower()


def set_cascade(mapper, class_):
    """
    Set cascade for relationships in Gtfsfeed.
    This allows to delete/add the relationships when their respective relation array changes.
    """
    if class_.__name__ == "Gtfsfeed":
        for rel in class_.__mapper__.relationships:
            if rel.key in [
                "redirectingids",
                "redirectingids_",
                "externalids",
                "externalids_",
            ]:
                rel.cascade = "all, delete-orphan"


def mapper_configure_listener(mapper, class_):
    """
    Mapper configure listener
    """
    set_cascade(mapper, class_)
    configure_polymorphic_mappers()


# Add the mapper_configure_listener to the mapper_configured event
event.listen(mapper, "mapper_configured", mapper_configure_listener)


def with_db_session(func):
    """
    Decorator to handle the session management for the decorated function.

    This decorator ensures that a database session is properly created, committed, rolled back in case of an exception,
    and closed. It uses the @contextmanager decorator to manage the lifecycle of the session, providing a clean and
    efficient way to handle database interactions.

    How it works:
        - The decorator checks if a 'db_session' keyword argument is provided to the decorated function.
        - If 'db_session' is not provided, it creates a new Database instance and starts a new session using the
          start_db_session context manager.
        - The context manager ensures that the session is properly committed if no exceptions occur, rolled back if an
          exception occurs, and closed in either case.
        - The session is then passed to the decorated function as the 'db_session' keyword argument.
        - If 'db_session' is already provided, it simply calls the decorated function with the existing session.
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
            with cls.lock:
                if not isinstance(cls.instance, cls):
                    cls.instance = object.__new__(cls)
        return cls.instance

    def __init__(self, database_url: Optional[str] = None, pool_size: int = 10):
        with Database.lock:
            if Database.initialized:
                return

            Database.initialized = True
            self.database_url: str = (
                database_url if database_url else os.getenv("FEEDS_DATABASE_URL")
            )
            if self.database_url is None:
                raise Exception("Database URL not provided.")

            self.pool_size = pool_size

            self._engines: dict[bool, "Engine"] = {}
            self._Sessions: dict[bool, "sessionmaker[Session]"] = {}

    def _get_engine(self, echo: bool) -> "Engine":
        if echo not in self._engines:
            engine = create_engine(
                self.database_url, echo=echo, pool_size=self.pool_size, max_overflow=0
            )
            self._engines[echo] = engine
        return self._engines[echo]

    def _get_session(self, echo: bool) -> "sessionmaker[Session]":
        if echo not in self._Sessions:
            engine = self._get_engine(echo)
            self._Sessions[echo] = sessionmaker(bind=engine, autoflush=True)
        return self._Sessions[echo]

    @contextmanager
    def start_db_session(self, echo: bool = True):
        """
        Context manager to start a database session with optional echo.

        This method manages the lifecycle of a database session, ensuring that the session is properly created,
        committed, rolled back in case of an exception, and closed. The @contextmanager decorator simplifies
        resource management by handling the setup and cleanup logic within a single function.
        """
        session = self._get_session(echo)()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()


def refresh_materialized_view(session: "Session", view_name: str) -> bool:
    """
    Refresh Materialized view by name.
    @return: True if the view was refreshed successfully, False otherwise
    """
    try:
        session.execute(text(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {view_name}"))
        return True
    except Exception as error:
        LOGGER.error(f"Error raised while refreshing view: {error}")
        return False
