"""
Background scheduler for features that need to act over time rather than
in direct response to a message:

1. Auto-delete: message_sender.py schedules a deletion row when a message
   is sent (if the bot has the feature enabled); this sweeps due rows and
   actually calls Telegram's deleteMessage (optionally reacting first).

2. Inactivity reminders: periodically finds users who've gone quiet and
   sends them a nudge, following a configurable multi-stage schedule
   (e.g. remind after 7 days, remind again after 14), tracking who's
   already received each stage, and detecting when a reminded user comes
   back (for the "reward" feature).

Runs as one of main.py's top-level tasks, same lifecycle as the poller
supervisor and job queue.
"""

import asyncio
from datetime import datetime, timedelta
from db import db

AUTODELETE_SWEEP_SECONDS = 15
# How often we even consider running the inactivity sweep loop; each bot
# additionally gates itself by its own configurable "inactive_hours".
INACTIVITY_SWEEP_SECONDS = 300  # 5 minutes


async def _delete_message(bot_id: int, chat_id: int, message_id: int, react_first: bool) -> bool:
    from bot_registry import bot_registry
    from telegram_adapter import telegram_pool
    bot = bot_registry.get_bot(bot_id)
    if not bot:
        return False
    adapter = await telegram_pool.get_adapter(bot["token"])
    
    if react_first:
        try:
            await adapter.set_message_reaction(chat_id, message_id, "👀")
        except Exception:
            pass  # reactions are a nice-to-have; never block the actual delete on this
    
    result = await adapter.delete_message(chat_id, message_id)
    if not result.get("ok"):
        # "message to delete not found" just means it's already gone
        # (user deleted it, or it was too old for Telegram to allow
        # deletion) - not worth logging as an error every sweep.
        desc = str(result.get("description", ""))
        if "not found" not in desc and "message can't be deleted" not in desc:
            print(f"⚠️ Bot #{bot_id}: failed to delete message {message_id} in {chat_id}: {result}")
    return bool(result.get("ok"))


async def _bump_autodel_stat(bot_id: int):
    today = datetime.now().date().isoformat()
    stored_date = await db.get_setting(bot_id, "autodel_stat_date")
    today_count = await db.get_setting(bot_id, "autodel_stat_today", 0)
    total = await db.get_setting(bot_id, "autodel_stat_total", 0)
    if stored_date != today:
        today_count = 0
    await db.set_setting(bot_id, "autodel_stat_date", today)
    await db.set_setting(bot_id, "autodel_stat_today", today_count + 1)
    await db.set_setting(bot_id, "autodel_stat_total", total + 1)


async def get_autodel_stats(bot_id: int) -> dict:
    today = datetime.now().date().isoformat()
    stored_date = await db.get_setting(bot_id, "autodel_stat_date")
    today_count = await db.get_setting(bot_id, "autodel_stat_today", 0) if stored_date == today else 0
    total = await db.get_setting(bot_id, "autodel_stat_total", 0)
    return {"today": today_count, "total": total}


async def _sweep_autodelete():
    due = await db.pop_due_scheduled_deletions()
    # Group by bot so we only fetch each bot's autodel_reaction setting once
    reaction_cache = {}
    for bot_id, chat_id, message_id in due:
        if bot_id not in reaction_cache:
            reaction_cache[bot_id] = await db.get_setting(bot_id, "autodel_reaction", False)
        ok = await _delete_message(bot_id, chat_id, message_id, react_first=reaction_cache[bot_id])
        if ok:
            await _bump_autodel_stat(bot_id)


async def _bump_inactive_stat(bot_id: int, field: str):
    key = f"inactive_stat_{field}"
    val = await db.get_setting(bot_id, key, 0)
    await db.set_setting(bot_id, key, val + 1)


async def get_inactive_stats(bot_id: int) -> dict:
    sent = await db.get_setting(bot_id, "inactive_stat_sent", 0)
    returned = await db.get_setting(bot_id, "inactive_stat_returned", 0)
    blocked = await db.get_setting(bot_id, "inactive_stat_blocked", 0)
    reminders = await db.get_setting(bot_id, "inactive_reminders", [])
    pending = 0
    for stage, r in enumerate(reminders):
        cutoff = (datetime.now() - timedelta(days=r["days"])).isoformat()
        pending += await db.count_inactive_candidates(bot_id, cutoff, stage=stage)
    return {"sent": sent, "returned": returned, "blocked": blocked, "pending": pending}


async def reset_inactive_stats(bot_id: int):
    for field in ("sent", "returned", "blocked"):
        await db.set_setting(bot_id, f"inactive_stat_{field}", 0)
    await db.clear_all_reminded(bot_id)


async def _sweep_inactivity():
    bot_ids = await db.get_bots_with_setting("inactive_enabled", True)
    from admin_panel.auth import is_admin
    from message_sender import message_sender
    
    now = datetime.now()
    
    for bot_id in bot_ids:
        keys = ["inactive_enabled", "inactive_hours", "inactive_reminders", "inactive_exc_subs"]
        defaults = {"inactive_enabled": False, "inactive_hours": 24, "inactive_reminders": [],
                    "inactive_exc_subs": False}
        s = await db.get_settings(bot_id, keys, defaults)
        if not s["inactive_enabled"] or not s["inactive_reminders"]:
            continue
        
        # "ساعات الإرسال": don't re-run this bot's sweep more often than
        # its configured interval - lets each bot control how chatty its
        # reminder checks are.
        last_run = await db.get_setting(bot_id, "inactive_last_run")
        if last_run:
            try:
                elapsed_hours = (now - datetime.fromisoformat(last_run)).total_seconds() / 3600
                if elapsed_hours < s["inactive_hours"]:
                    continue
            except ValueError:
                pass
        await db.set_setting(bot_id, "inactive_last_run", now.isoformat())
        
        for stage, reminder in enumerate(s["inactive_reminders"]):
            cutoff = (now - timedelta(days=reminder["days"])).isoformat()
            candidates = await db.get_inactive_candidates(bot_id, cutoff, stage=stage)
            
            for chat_id in candidates:
                # Never nag the admin(s) themselves
                if await is_admin(bot_id, chat_id):
                    continue
                
                if s["inactive_exc_subs"]:
                    from subscription_handler import subscription_handler
                    subs = await subscription_handler.get_subscriptions(bot_id)
                    if any(sub["active"] for sub in subs):
                        if await subscription_handler.check_subscription(bot_id, chat_id):
                            continue
                
                result = await message_sender.send_message(bot_id, chat_id, reminder["text"])
                await db.mark_reminded(bot_id, chat_id, stage=stage)
                if result is None:
                    # send_message returns None both on a 403 (blocked) and on
                    # other failures; either way we don't count it as "sent"
                    await _bump_inactive_stat(bot_id, "blocked")
                else:
                    await _bump_inactive_stat(bot_id, "sent")


async def handle_possible_return(bot_id: int, chat_id: int):
    """Call this whenever a user sends a message - if they'd previously
    been reminded as inactive (any stage), this is them coming back.
    Clears every stage's flag and, if the reward toggle is on, sends a
    reward."""
    if not await db.has_any_reminder(bot_id, chat_id):
        return
    await db.clear_reminded(bot_id, chat_id)
    await _bump_inactive_stat(bot_id, "returned")
    
    reward_on = await db.get_setting(bot_id, "inactive_reward", False)
    if reward_on:
        from message_sender import message_sender
        await message_sender.send_message(
            bot_id, chat_id, "🎁 هلا فيك رجعت! هذي هدية صغيرة على رجعتك 🎉"
        )


async def run_forever():
    """Runs both sweeps forever on their own intervals. Each sweep catches
    its own errors so one bad bot/message can't kill the whole loop."""
    print("⏱️ Scheduler started (auto-delete + inactivity reminders)")
    elapsed_since_inactivity = 0
    
    while True:
        await asyncio.sleep(AUTODELETE_SWEEP_SECONDS)
        
        try:
            await _sweep_autodelete()
        except Exception as e:
            print(f"⚠️ autodelete sweep error: {type(e).__name__}: {e}")
        
        elapsed_since_inactivity += AUTODELETE_SWEEP_SECONDS
        if elapsed_since_inactivity >= INACTIVITY_SWEEP_SECONDS:
            elapsed_since_inactivity = 0
            try:
                await _sweep_inactivity()
            except Exception as e:
                print(f"⚠️ inactivity sweep error: {type(e).__name__}: {e}")
