from sqlalchemy.sql.functions import ReturnTypeFromArgs


class unaccent(ReturnTypeFromArgs):
    """
    This class represents the `unaccent` function in the database.
    This function is used to remove accents from a string.
    More documentation can be found at https://www.postgresql.org/docs/current/unaccent.html.
    Be aware that this function is not available in all databases nor in all versions of PostgreSQL.
    """

    pass
