from sqlalchemy import create_engine

sqlalchemy_engine = create_engine("sqlite+pysqlite:///:memory:", echo=True)

if __name__ == '__main__':
    pass