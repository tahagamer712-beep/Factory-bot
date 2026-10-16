"""Granular permission model for created-bot admins.

- The bot OWNER always has every permission (implicit, cannot be revoked).
- Legacy extra admins (bot_admins.permissions IS NULL) keep full access
  for backward compatibility.
- New/restricted admins get only the permissions explicitly granted.
"""

PERMISSIONS = {
    "view_stats": "عرض الإحصائيات",
    "manage_users": "إدارة المستخدمين",
    "review_reports": "مراجعة البلاغات",
    "ban": "الحظر ورفع الحظر",
    "broadcast": "الإذاعة",
    "edit_settings": "تعديل الإعدادات",
    "view_logs": "عرض السجلات",
    "create_backup": "إنشاء نسخ احتياطية",
    "restore": "تنفيذ الاستعادة",
    "manage_admins": "إدارة المشرفين",
}

ALL_PERMISSIONS = list(PERMISSIONS.keys())

# Sensible starter sets shown in the UI when adding a restricted admin.
PRESETS = {
    "viewer": (["view_stats", "view_logs"], "👁 مشاهد فقط"),
    "moderator": (["view_stats", "manage_users", "review_reports", "ban", "view_logs"],
                  "🛡 مشرف محتوى"),
    "broadcaster": (["view_stats", "broadcast", "view_logs"], "📢 مسؤول إذاعة"),
}


def label(perm: str) -> str:
    return PERMISSIONS.get(perm, perm)


def describe(perms) -> str:
    """Human-readable summary of a permission list (or legacy/owner)."""
    if perms is None:
        return "كامل الصلاحيات (تقليدي)"
    if not perms:
        return "بدون صلاحيات"
    names = [PERMISSIONS.get(p, p) for p in perms if p in PERMISSIONS]
    if len(names) <= 3:
        return "، ".join(names)
    return f"{len(names)} صلاحيات: " + "، ".join(names[:3]) + "…"
