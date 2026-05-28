#
#   MobilityData 2024
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
import logging
import os
import threading
from contextlib import contextmanager

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from shared.common.logging_utils import get_env_logging_level


class UsersDatabase:
    """
    Database instance for the users database (USERS_DATABASE_URL).

    Intentionally a separate singleton from the feeds `Database` class to avoid
    cross-initialization between the two database connections.
    """

    instance = None
    initialized = False
    lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if not isinstance(cls.instance, cls):
            with cls.lock:
                if not isinstance(cls.instance, cls):
                    cls.instance = object.__new__(cls)
        return cls.instance

    def __init__(self, echo_sql=False, users_database_url: str | None = None):
        with UsersDatabase.lock:
            if UsersDatabase.initialized:
                return

            UsersDatabase.initialized = True
            load_dotenv()
            self.logger = logging.getLogger(__name__)
            database_url = users_database_url if users_database_url else os.getenv("USERS_DATABASE_URL")
            if database_url is None:
                raise Exception("USERS_DATABASE_URL not provided.")
            pool_size = int(os.getenv("DB_POOL_SIZE", 10))
            self.engine = create_engine(database_url, echo=echo_sql, pool_size=pool_size, max_overflow=0)
            self.Session = sessionmaker(bind=self.engine, autoflush=False)

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


def with_users_db_session(func=None, db_url: str | None = None):
    """
    Decorator to handle session management for the users database.

    Mirrors `with_db_session` from `shared.database.database` but targets
    USERS_DATABASE_URL via `UsersDatabase`.
    """
    if func is None:
        return lambda f: with_users_db_session(f, db_url=db_url)

    def wrapper(*args, **kwargs):
        db_session = kwargs.get("db_session")
        if db_session is None:
            db = UsersDatabase(
                echo_sql=get_env_logging_level() == logging.getLevelName("DEBUG"),
                users_database_url=db_url,
            )
            with db.start_db_session() as session:
                kwargs["db_session"] = session
                return func(*args, **kwargs)
        else:
            return func(*args, **kwargs)

    return wrapper
