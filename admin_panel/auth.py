"""Who is allowed to see the admin panel for a given bot."""

from db import db


async def is_admin(bot_id: int, user_id: int) -> bool:
    """True if user_id is the bot's owner (from bot_registry) or a
    registered extra admin (bot_admins table)."""
    from bot_registry import bot_registry
    bot = bot_registry.get_bot(bot_id)
    owner_id = bot.get("owner_id") if bot else None
    return await db.is_admin(bot_id, user_id, owner_id=owner_id)


async def is_owner(bot_id: int, user_id: int) -> bool:
    """True if user_id is the bot's registered owner (top-level, irrevocable)."""
    return await db.is_owner(bot_id, user_id)


async def has_permission(bot_id: int, user_id: int, perm: str) -> bool:
    """Granular permission check for backend enforcement.

    - Owner: always True.
    - Non-admin: always False.
    - Legacy extra admin (no permissions recorded): True (backward compatible).
    - Restricted admin: True only if perm is in their granted list.
    """
    from . import permissions as pm
    if perm not in pm.ALL_PERMISSIONS:
        return False
    if await is_owner(bot_id, user_id):
        return True
    perms = await db.get_admin_permissions(bot_id, user_id)
    if perms is None:
        # Not an extra admin at all -> False; legacy admin -> True
        return await db.is_admin(bot_id, user_id)
    return perm in perms
