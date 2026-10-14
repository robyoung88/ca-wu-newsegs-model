import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import sqlalchemy as sa

from newsegsmodelapp.backend.db.db import write_transaction


class TestWriteTransaction(unittest.TestCase):
    def test_concurrent_writes_are_serialized(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            engine = sa.create_engine(
                f"sqlite+pysqlite:///{Path(temp_dir) / 'test.db'}",
                connect_args={"timeout": 0.05},
            )
            try:
                with engine.begin() as conn:
                    conn.exec_driver_sql(
                        "CREATE TABLE writes (value INTEGER NOT NULL)"
                    )

                def insert(value: int) -> None:
                    with write_transaction(engine) as conn:
                        conn.execute(
                            sa.text("INSERT INTO writes (value) VALUES (:value)"),
                            {"value": value},
                        )
                        time.sleep(0.1)

                with ThreadPoolExecutor(max_workers=4) as executor:
                    list(executor.map(insert, range(8)))

                with engine.connect() as conn:
                    row_count = conn.execute(
                        sa.text("SELECT COUNT(*) FROM writes")
                    ).scalar_one()

                self.assertEqual(row_count, 8)
            finally:
                engine.dispose()
