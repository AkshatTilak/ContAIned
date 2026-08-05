import asyncio
from sqlalchemy import inspect
from common.clients.postgres import get_engine
from common.models.database import Base
import projects.syntraflow.src.database.models
import projects.evalops.src.database.models
import projects.guardroute.src.database.models

async def check():
    engine = get_engine()
    async with engine.connect() as conn:
        def _get_inspector(sync_conn):
            inspector = inspect(sync_conn)
            db_tables = inspector.get_table_names()
            print("=== DB TABLES IN POSTGRES ===")
            print(sorted(db_tables))
            print("\n=== MISSING / MISMATCHED COLUMNS ===")
            
            model_tables = Base.metadata.tables
            for table_name, table in model_tables.items():
                if table_name not in db_tables:
                    print(f"TABLE MISSING IN DB: {table_name}")
                else:
                    db_cols = {c["name"]: c for c in inspector.get_columns(table_name)}
                    model_cols = {c.name: c for c in table.columns}
                    missing_in_db = set(model_cols.keys()) - set(db_cols.keys())
                    if missing_in_db:
                        print(f"Table '{table_name}' MISSING COLUMNS IN DB: {sorted(missing_in_db)}")

        await conn.run_sync(_get_inspector)

if __name__ == "__main__":
    asyncio.run(check())
