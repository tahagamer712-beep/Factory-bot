"""Telegram command menus shared by the factory and created bots."""

from typing import Iterable

from bot_registry import bot_registry
from db import db
from telegram_adapter import telegram_pool


FACTORY_COMMANDS = [
    {"command": "start", "description": "بدء استخدام المصنع"},
    {"command": "help", "description": "شرح بسيط عن المصنع"},
]

CREATED_BOT_COMMANDS = [
    {"command": "start", "description": "البداية"},
]

FACTORY_ADMIN_COMMANDS = FACTORY_COMMANDS + [
    {"command": "admin", "description": "لوحة إدارة المصنع"},
]


def _private_scope(user_id: int) -> dict:
    return {"type": "chat", "chat_id": user_id}


async def _set_commands(bot_id: int, commands: list, scope: dict | None = None):
    bot = bot_registry.get_bot(bot_id)
    if not bot:
        return
    adapter = await telegram_pool.get_adapter(bot["token"])
    await adapter.set_my_commands(commands, scope=scope)


async def sync_factory_commands(admin_ids: Iterable[int] = ()):
    """Set the public factory menu and the private admin menu."""
    from config import FACTORY_BOT_ID

    if FACTORY_BOT_ID is None:
        return
    await _set_commands(FACTORY_BOT_ID, FACTORY_COMMANDS)
    for user_id in admin_ids:
        await _set_commands(
            FACTORY_BOT_ID,
            FACTORY_ADMIN_COMMANDS,
            scope=_private_scope(user_id),
        )


async def sync_created_bot_commands(bot_id: int):
    """Created bots expose only /start publicly; admins also use /start."""
    await _set_commands(bot_id, CREATED_BOT_COMMANDS)


async def sync_all_commands():
    """Refresh menus for the factory and every registered created bot."""
    from config import ADMIN_ID, FACTORY_BOT_ID

    admin_rows = await db.list_factory_admins()
    admin_ids = [row["user_id"] for row in admin_rows]
    if ADMIN_ID is not None:
        admin_ids.append(ADMIN_ID)
    if FACTORY_BOT_ID is not None:
        await sync_factory_commands(admin_ids)

    for bot in bot_registry.list_bots():
        if bot["bot_id"] != FACTORY_BOT_ID:
            await sync_created_bot_commands(bot["bot_id"])