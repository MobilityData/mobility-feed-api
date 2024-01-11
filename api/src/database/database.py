import itertools
import os
import threading
import uuid
from typing import Type, Callable
from dotenv import load_dotenv

from google.cloud.sql.connector import Connector
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session, load_only, Query

from database_gen.sqlacodegen_models import Base
from utils.logger import Logger


lock = threading.Lock()
global_session = None


def generate_unique_id() -> str:
    """
    Generates a unique ID of 36 characters
    :return: the ID
    """
    return str(uuid.uuid4())


class Database:
    """
    This class represents a database instance
    """

    instance = None

    def __new__(cls, *args, **kwargs):
        if not isinstance(cls.instance, cls):
            with lock:
                if not isinstance(cls.instance, cls):
                    cls.instance = object.__new__(cls)
        return cls.instance

    def __init__(self):
        load_dotenv()
        username = os.getenv("POSTGRES_USER")
        password = os.getenv("POSTGRES_PASSWORD")
        schema = os.getenv("POSTGRES_DB")
        port = os.getenv("POSTGRES_PORT")
        host = os.getenv("POSTGRES_HOST")
        self.logger = Logger(Database.__module__).get_logger()
        self.engine = None
        self.connection_attempts = 0
        self.SQLALCHEMY_DATABASE_URL = f"postgresql://{username}:{password}@{host}:{port}/{schema}"

        # set up GCP SQL Connector
        connector = Connector()
        instance_name = os.getenv("INSTANCE_NAME")
        self.get_connection = None
        if instance_name is not None:
            self.get_connection = lambda: connector.connect(
                instance_name,
                "pg8000",
                user=username,
                password=password,
                db=schema,
            )
        self.start_session()

    def is_connected(self):
        """
        Checks the connection status
        :return: True if the database is accessible False otherwise
        """
        return self.engine is not None and global_session is not None

    def start_session(self):
        """
        Starts a singleton session
        :return: True if the session was started, False otherwise
        """
        global global_session
        try:
            if self.engine is None:
                self.connection_attempts += 1
                self.logger.debug(f"Database connection attempt #{self.connection_attempts}.")
                if self.get_connection is not None:
                    self.engine = create_engine("postgresql+pg8000://", creator=self.get_connection)
                else:
                    self.engine = create_engine(self.SQLALCHEMY_DATABASE_URL, echo=True)
                self.logger.debug("Database connected.")
            if global_session is not None and global_session.is_active:
                self.logger.info("Database session reused.")
                return global_session
            lock.acquire()
            global_session = Session(self.engine, autoflush=False)
            self.logger.info("Singleton Database session started.")
        except Exception as error:
            raise Exception(f"Error creating database session: {error}")
        finally:
            lock.release()
        return self.is_connected()


    def close_session(self):
        """
        Closes a session
        :return: True if the session was started, False otherwise
        """
        try:
            if global_session is not None and global_session.is_active:
                global_session.close()
        except Exception as e:
            self.logger.error(f"Session closing failed with exception: \n {e}")
        return self.is_connected()

    def select(
        self,
        model: Type[Base] = None,
        query: Query = None,
        conditions: list = None,
        attributes: list = None,
        update_session: bool = True,
        limit: int = None,
        offset: int = None,
        group_by: Callable = None,
    ):
        """
        Executes a query on the database
        :param model: the sqlalchemy model to query
        :param query: the sqlalchemy ORM query execute
        :param conditions: list of conditions (filters for the query)
        :param attributes: list of model's attribute names that you want to fetch. If not given, fetches all attributes.
        :param update_session: option to update session before running the query (defaults to True)
        :param limit: the optional number of rows to limit the query with
        :param offset: the optional number of rows to offset the query with
        :param group_by: an optional function, when given query results will group by return value of group_by function.
        Query needs to order the return values by the key being grouped by
        :return: None if database is inaccessible, the results of the query otherwise
        """
        try:
            if update_session:
                self.start_session()
            if query is None:
                query = global_session.query(model)
            if conditions:
                for condition in conditions:
                    query = query.filter(condition)
            if attributes is not None:
                query = query.options(load_only(*attributes))
            if limit is not None:
                query = query.limit(limit)
            if offset is not None:
                query = query.offset(offset)
            results = global_session.execute(query).all()
            if group_by:
                return [list(group) for _, group in itertools.groupby(results, group_by)]
            return results
        except Exception as e:
            self.logger.error(f"SELECT query failed with exception: \n{e}")
            return None
        finally:
            if not update_session:
                self.close_session()

    def select_from_active_session(self, model: Base, conditions: list = None, attributes: list = None):
        """
        Select an object within the uncommitted session objects
        :param model: the sqlalchemy model to query
        :param conditions: list of conditions (filters for the query)
        :param attributes: list of model's attribute names that you want to fetch. If not given, fetches all attributes.
        :return: Empty list if database is inaccessible, the results of the query otherwise
        """
        try:
            if not global_session or not global_session.is_active:
                raise Exception("Inactive session")
            results = [obj for obj in global_session.new if isinstance(obj, model)]
            if conditions:
                for condition in conditions:
                    attribute_name = condition.left.name
                    attribute_value = condition.right.value
                    results = [result for result in results if getattr(result, attribute_name) == attribute_value]
            if attributes:
                results = [{attr: getattr(obj, attr) for attr in attributes} for obj in results]
            return results
        except Exception as e:
            self.logger.error(f"Object selection within the uncommitted session objects failed with exception: \n{e}")
            return []

    def merge(
        self,
        orm_object: Base,
        update_session: bool = False,
        auto_commit: bool = False,
        load: bool = True,
    ):
        """
        Updates or inserts an object in the database
        :param orm_object: the modeled object to update or insert
        :param update_session: option to update the session before running the merge query (defaults to False)
        :param auto_commit: option to automatically commit merge (defaults to False)
        :param load: controls whether the database should be queried for the object being merged (defaults to True)
        :return: True if merge was successful, False otherwise
        """
        try:
            if update_session:
                self.start_session()
            global_session.merge(orm_object, load=load)
            if auto_commit:
                global_session.commit()
            return True
        except Exception as e:
            self.logger.error(f"Merge query failed with exception: \n{e}")
            return False
        finally:
            if not update_session:
                self.close_session()

    def commit(self):
        """
        Commits the changes in the current session i.e. synch the changes with the database
        and close the session
        :return: True if commit was successful, False otherwise
        """
        try:
            if global_session is not None and global_session.is_active:
                global_session.commit()
                return True
            return False
        except Exception as e:
            self.logger.error(f"Commit failed with exception: \n{e}")
            return False
        finally:
            if global_session is not None:
                global_session.close()

    def flush(self):
        """
        Flush the active session i.e. synch the changes with the database but keep the
        session active
        :return: True if flush was successful, False otherwise
        """
        try:
            if global_session is not None and global_session.is_active:
                global_session.flush()
                return True
            return False
        except Exception as e:
            self.logger.error(f"Flush failed with exception: \n{e}")
            return False

    def merge_relationship(
        self,
        parent_model: Base.__class__,
        parent_key_values: dict,
        child: Base,
        relationship_name: str,
        update_session: bool = False,
        auto_commit: bool = False,
        uncommitted: bool = False,
    ):
        """
        Adds a child instance to a parent's related items. If the parent doesn't exist, it creates a new one.
        :param parent_model: the orm model class of the parent containing the relationship
        :param parent_key_values: the dictionary of primary keys and their values of the parent
        :param child: the child instance to be added
        :param relationship_name: the name of the attribute on the parent model that holds related children
        :param update_session: option to update the session before running the merge query (defaults to False)
        :param auto_commit: option to automatically commit merge (defaults to False)
        :param uncommitted: option to merge relationship with uncommitted objects in the session (defaults to False)
        :return: True if the operation was successful, False otherwise
        """
        try:
            primary_keys = inspect(parent_model).primary_key
            conditions = [key == parent_key_values[key.name] for key in primary_keys]

            # Query for the existing parent using primary keys
            if uncommitted:
                parent = self.select_from_active_session(parent_model, conditions)
            else:
                parent = self.select(parent_model, conditions, update_session=update_session)
            if not parent:
                return False
            else:
                parent = parent[0]

            # add child to the list of related children from the parent
            relationship_elements = getattr(parent, relationship_name)
            relationship_elements.append(child)
            if not uncommitted:
                return self.merge(parent, update_session=update_session, auto_commit=auto_commit)
            return True
        except Exception as e:
            self.logger.error(
                f"Adding {child.__class__.__name__} to {parent_model.__name__} failed with exception: \n{e}"
            )
            return False
