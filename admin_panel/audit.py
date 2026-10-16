"""Independent admin audit log. Append-only: no UI path edits or deletes it.

Every sensitive admin action should call log_action(). Tokens, passwords and
private conversation content are NEVER recorded (sanitized in db.log_audit).
"""

from db import db


async def log_action(bot_id: int, admin_id: int, action: str, target=None,
                     success: bool = True, reason: str = None, summary: str = None) -> bool:
    return await db.log_audit(bot_id, admin_id, action,
                              target=str(target) if target is not None else None,
                              success=success, reason=reason, summary=summary)


# Canonical action names used across the panel
A_BAN = "ban"
A_UNBAN = "unban"
A_REPORT_DECISION = "report_decision"
A_BROADCAST = "broadcast"
A_SETTING_CHANGE = "setting_change"
A_ADMIN_ADD = "admin_add"
A_ADMIN_REMOVE = "admin_remove"
A_ADMIN_PERMS = "admin_perms"
A_BACKUP_CREATE = "backup_create"
A_BACKUP_RESTORE = "backup_restore"
A_MAINTENANCE = "maintenance"

ACTION_LABELS = {
    A_BAN: "حظر", A_UNBAN: "رفع حظر",
    A_REPORT_DECISION: "قرار بلاغ", A_BROADCAST: "إذاعة",
    A_SETTING_CHANGE: "تغيير إعداد", A_ADMIN_ADD: "إضافة مشرف",
    A_ADMIN_REMOVE: "إزالة مشرف", A_ADMIN_PERMS: "تعديل صلاحيات",
    A_BACKUP_CREATE: "إنشاء نسخة", A_BACKUP_RESTORE: "استعادة",
    A_MAINTENANCE: "وضع الصيانة",
}


def action_label(action: str) -> str:
    return ACTION_LABELS.get(action, action)
