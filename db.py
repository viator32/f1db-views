"""
Very small helper to run any (read-only) SQL and get a pandas DataFrame.
"""
import os
from functools import lru_cache

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
from dotenv import load_dotenv

load_dotenv()        # reads .env


@lru_cache
def _engine():
    """Create and cache a SQLAlchemy engine with a properly escaped URL."""
    url = URL.create(
        drivername="postgresql+psycopg2",
        username=os.getenv("PGUSER"),
        password=os.getenv("PGPASSWORD"),
        host=os.getenv("PGHOST"),
        port=os.getenv("PGPORT"),
        database=os.getenv("PGDATABASE"),
    )
    return create_engine(url, pool_pre_ping=True)


def run_query(sql: str, **params) -> pd.DataFrame:
    """Execute parameterised SQL safely and return a DataFrame."""
    with _engine().connect() as conn:
        return pd.read_sql(text(sql), conn, params=params)
