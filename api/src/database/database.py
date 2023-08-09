import os
import uuid

from google.cloud.sql.connector import Connector
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session, load_only

from database_gen.sqlacodegen_models import Base
from utils.logger import Logger


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

    def __init__(self):
        POSTGRES_USER = os.getenv("POSTGRES_USER")
        POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD")
        POSTGRES_DB = os.getenv("POSTGRES_DB")
        POSTGRES_PORT = os.getenv("POSTGRES_PORT")
        POSTGRES_HOST = os.getenv("POSTGRES_HOST")
        self.logger = Logger(Database.__module__).get_logger()
        self.engine = None
        self.session = None
        self.connection_attempts = 0
        self.SQLALCHEMY_DATABASE_URL = f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"

        # set up GCP SQL Connector
        connector = Connector()
        INSTANCE_NAME = os.getenv("INSTANCE_NAME")
        self.get_connection = None
        if INSTANCE_NAME is not None:
            self.get_connection = lambda: connector.connect(
                INSTANCE_NAME,
                "pg8000",
                user=POSTGRES_DB,
                password=POSTGRES_PASSWORD,
                db=POSTGRES_DB
            )
        self.start_session()

    def is_connected(self):
        """
        Checks the connection status
        :return: True if the database is accessible False otherwise
        """
        return self.engine is not None and self.session is not None

    def start_session(self):
        """
        Starts a session
        :return: True if the session was started, False otherwise
        """
        try:
            if self.engine is None:
                self.connection_attempts += 1
                self.logger.debug(f"Database connection attempt #{self.connection_attempts}.")
                if self.get_connection is not None:
                    self.engine = create_engine("postgresql+pg8000://", creator=self.get_connection)
                else:
                    self.engine = create_engine(self.SQLALCHEMY_DATABASE_URL, echo=True)
                self.logger.debug("Database connected.")
            if self.session is not None and self.session.is_active:
                self.session.close()
            self.session = Session(self.engine, autoflush=False)
        except Exception as e:
            self.logger.error(f"Database new session creation failed with exception: \n {e}")
        return self.is_connected()

    def close_session(self):
        """
        Starts a session
        :return: True if the session was started, False otherwise
        """
        try:
            if self.session is not None and self.session.is_active:
                self.session.close()
        except Exception as e:
            self.logger.error(f"Session closing failed with exception: \n {e}")
        return self.is_connected()

    def select(self, model: Base, conditions: list = None, attributes: list = None, update_session: bool = True):
        """
        Executes a query on the database
        :param model: the sqlalchemy model to query
        :param conditions: list of conditions (filters for the query)
        :param attributes: list of model's attribute names that you want to fetch. If not given, fetches all attributes.
        :param update_session: option to update session before running the query (defaults to True)
        :return: None if database is inaccessible, the results of the query otherwise
        """
        try:
            if update_session:
                self.start_session()
            query = self.session.query(model)
            if conditions:
                for condition in conditions:
                    query = query.filter(condition)
            if attributes:
                query = query.options(load_only(*attributes))
            return query.all()
        except Exception as e:
            self.logger.error(f'SELECT query failed with exception: \n{e}')
            return None

    def merge(self, orm_object: Base, update_session: bool = True, auto_commit: bool = True):
        """
        Updates or inserts an object in the database
        :param orm_object: the modeled object to update or insert
        :param update_session: option to update the session before running the merge query (defaults to True)
        :param auto_commit: option to automatically commit merge (defaults to True)
        :return: True if merge was successful, False otherwise
        """
        try:
            if update_session:
                self.start_session()
            self.session.merge(orm_object)
            if auto_commit:
                self.session.commit()
            return True
        except Exception as e:
            self.logger.error(f'Merge query failed with exception: \n{e}')
            return False

    def commit(self):
        """
        Commits the changes in the current session
        :return: True if commit was successful, False otherwise
        """
        try:
            if self.session is not None and self.session.is_active:
                self.session.commit()
                return True
            return False
        except Exception as e:
            self.logger.error(f'Commit failed with exception: \n{e}')
            return False
        finally:
            if self.session is not None:
                self.session.close()

    def merge_relationship(
            self,
            parent_model: Base.__class__,
            parent_key_values: dict,
            child: Base,
            relationship_name: str,
            update_session: bool = True,
            auto_commit: bool = True
    ):
        """
        Adds a child instance to a parent's related items. If the parent doesn't exist, it creates a new one.
        :param parent_model: the orm model class of the parent containing the relationship
        :param parent_key_values: the dictionary of primary keys and their values of the parent
        :param child: the child instance to be added
        :param relationship_name: the name of the attribute on the parent model that holds related children
        :param update_session: option to update the session before running the merge query (defaults to True)
        :param auto_commit: option to automatically commit merge (defaults to True)
        :return: True if the operation was successful, False otherwise
        """
        try:
            primary_keys = inspect(parent_model).primary_key
            conditions = [key == parent_key_values[key.name] for key in primary_keys]

            # Query for the existing parent using primary keys
            parent = self.select(parent_model, conditions, update_session=update_session)
            if not parent:
                return False
            else:
                parent = parent[0]

            # add child to the list of related children from the parent
            relationship_elements = getattr(parent, relationship_name)
            relationship_elements.append(child)
            return self.merge(parent, update_session=update_session, auto_commit=auto_commit)
        except Exception as e:
            self.logger.error(f'Adding {child.__class__.__name__} to {parent_model.__name__} failed with exception: \n{e}')
            return False


