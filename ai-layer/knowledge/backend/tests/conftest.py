"""Keep destructive startup/recovery tests away from running service records."""
import os
from uuid import uuid4

import psycopg
from psycopg import sql
import pytest


@pytest.fixture(scope='session', autouse=True)
def isolated_work_database():
    original = os.environ.get('DB_NAME')
    if not original:
        yield
        return
    from backend.src.modules.process_runtime.checkpointer import checkpoint_postgres_uri

    # Keep an administrative connection to the original server, but never run
    # tests against its application database. No silent shared-DB fallback.
    admin = psycopg.connect(checkpoint_postgres_uri(), autocommit=True)
    name = 'ar100_pytest_' + uuid4().hex
    created = False
    try:
        admin.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)))
        created = True
        os.environ['DB_NAME'] = name
        yield
    finally:
        os.environ['DB_NAME'] = original
        if created:
            admin.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(name)))
        admin.close()
