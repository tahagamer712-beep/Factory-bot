"""Who can see the FACTORY admin panel (separate from any single bot's
admin_panel). The factory bot's own owner (self-owned, see main.py
bootstrap) is always an implicit full "owner"-role admin; everyone else
needs a row in factory_admins."""

from db import db

ROLE_ALL_PERMISSIONS = [
    "bots", "owners", "stats", "broadcast", "blocks", "subscriptions",
    "backups", "dbtools", "settings", "logs", "system_settings", "admins",
    "delete_bots",
]

ROLE_DEFAULTS = {
    "owner": ROLE_ALL_PERMISSIONS,
    "admin": ["bots", "owners", "stats", "broadcast", "logs"],
    "support": ["bots", "owners"],
    "analyst": ["logs"],
}


async def is_factory_admin(user_id: int) -> bool:
    from config import FACTORY_ADMIN_ID, FACTORY_BOT_ID
    if user_id in {FACTORY_ADMIN_ID, FACTORY_BOT_ID} - {None}:
        return True
    return await db.get_factory_admin(user_id) is not None


async def get_role(user_id: int) -> str:
    from config import FACTORY_ADMIN_ID, FACTORY_BOT_ID
    if user_id in {FACTORY_ADMIN_ID, FACTORY_BOT_ID} - {None}:
        return "owner"
    admin = await db.get_factory_admin(user_id)
    return admin["role"] if admin else "none"


async def has_permission(user_id: int, permission: str) -> bool:
    from config import FACTORY_ADMIN_ID, FACTORY_BOT_ID
    if user_id in {FACTORY_ADMIN_ID, FACTORY_BOT_ID} - {None}:
        return True  # factory owner can do everything, always
    admin = await db.get_factory_admin(user_id)
    if not admin:
        return False
    return permission in admin["permissions"]
