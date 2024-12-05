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

from sqlalchemy import create_engine, text, event
from sqlalchemy.orm import sessionmaker, mapper, class_mapper
import logging

from database_gen.sqlacodegen_models import Feed, Gtfsfeed, Gtfsrealtimefeed, Gbfsfeed

DB_REUSE_SESSION: Final[str] = "DB_REUSE_SESSION"
lock = threading.Lock()
global_session = None


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


def get_db_engine(database_url: str = None, echo: bool = True):
    """
    :return: Database engine
    """
    if database_url is None:
        raise Exception("Database URL is not provided")
    return create_engine(database_url, echo=echo)


def start_new_db_session(database_url: str = None, echo: bool = True):
    if database_url is None:
        raise Exception("Database URL is not provided")
    logging.info("Starting new database session.")
    return sessionmaker(bind=get_db_engine(database_url, echo=echo))()


def start_singleton_db_session(database_url: str = None):
    """
    :return: Database singleton session
    """
    global global_session
    try:
        if global_session is not None:
            logging.info("Database session reused.")
            return global_session
        global_session = start_new_db_session(database_url)
        logging.info("Singleton Database session started.")
        return global_session
    except Exception as error:
        raise Exception(f"Error creating database session: {error}")


def start_db_session(database_url: str = None, echo: bool = True):
    """
    :return: Database session
    """
    global lock
    try:
        lock.acquire()
        if is_session_reusable():
            return start_singleton_db_session(database_url)
        logging.info("Not reusing the previous session, starting new database session.")
        return start_new_db_session(database_url, echo)
    except Exception as error:
        raise Exception(f"Error creating database session: {error}")
    finally:
        lock.release()


def is_session_reusable():
    return os.getenv("%s" % DB_REUSE_SESSION, "false").lower() == "true"


def close_db_session(session, raise_exception: bool = False):
    """
    Closes the database session
    """
    try:
        session_reusable = is_session_reusable()
        logging.info(f"Closing session with DB_REUSE_SESSION={session_reusable}")
        if session_reusable and session == global_session:
            logging.info("Skipping database session closing.")
            return
        session.close()
        logging.info("Database session closed.")
    except Exception as error:
        logging.error(f"Error closing database session: {error}")
        if raise_exception:
            raise error


def refresh_materialized_view(session, view_name: str, concurrently=True) -> bool:
    """
    Refresh Materialized view by name.
    @return: True if the view was refreshed successfully, False otherwise
    """
    try:
        session.execute(
            text(
                f"REFRESH MATERIALIZED VIEW {'CONCURRENTLY' if concurrently else ''} {view_name}"
            )
        )
        return True
    except Exception as error:
        logging.error(f"Error raised while refreshing view: {error}")
    return False
