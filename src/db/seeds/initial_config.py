from __future__ import annotations

import os
from typing import Iterable

from src.db.pool import PoolConfig, close_pool, init_pool


async def seed_default_configs(guild_ids: Iterable[int]) -> None:
    pool = await init_pool(PoolConfig.from_env())
    async with pool.acquire() as conn:
        for gid in guild_ids:
            await conn.execute(
                """
                INSERT INTO economy.economy_configurations (guild_id, admin_role_ids, created_at, updated_at)
                VALUES ($1, '[]'::jsonb, timezone('utc', now()), timezone('utc', now()))
                ON CONFLICT (guild_id) DO NOTHING
                """,
                gid,
            )
    await close_pool()


async def main() -> None:
    allowlist_raw = os.getenv("DISCORD_GUILD_ALLOWLIST", "")
    guild_ids = [int(x.strip()) for x in allowlist_raw.split(",") if x.strip()]
    await seed_default_configs(guild_ids)


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
