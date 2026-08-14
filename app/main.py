import asyncio
import logging

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from app.agent.graph import build_graph
from app.bot.telegram_bot import run_bot
from app.config import settings
from app.storage.db import init_db

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")


async def main() -> None:
    await init_db()
    async with AsyncSqliteSaver.from_conn_string(settings.database_path) as checkpointer:
        graph = await build_graph(checkpointer)
        await run_bot(graph)


if __name__ == "__main__":
    asyncio.run(main())
