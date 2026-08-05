import asyncio
from sqlalchemy import select
from common.clients.postgres import get_sessionmaker
from projects.syntraflow.src.database.models import SyntraFlowCollection

async def check():
    s = get_sessionmaker()
    async with s() as session:
        stmt = select(SyntraFlowCollection)
        res = await session.execute(stmt)
        cols = res.scalars().all()
        print("SQL Collections in DB:")
        for c in cols:
            print(f"  id={c.id}, name={c.name}, hub_id={c.hub_id}, binding={c.datastore_binding_id}")

if __name__ == "__main__":
    asyncio.run(check())
