from database.database import Database


class GBFSDatabasePopulateHelper:
    def __init__(self, file_path):
        self.db = Database(echo_sql=False)


if __name__ == '__main__':
    pass
