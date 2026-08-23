"""Who is allowed to see the admin panel for a given bot."""

from db import db


async def is_admin(bot_id: int, user_id: int) -> bool:
    """True if user_id is the bot's owner (from bot_registry) or a
    registered extra admin (bot_admins table)."""
    from bot_registry import bot_registry
    bot = bot_registry.get_bot(bot_id)
    owner_id = bot.get("owner_id") if bot else None
    return await db.is_admin(bot_id, user_id, owner_id=owner_id)
