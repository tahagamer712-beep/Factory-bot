#!/usr/bin/env python3
"""Regression tests for the factory-admin and verification authorization fixes."""

import inspect
import unittest

from admin_panel import keyboards
from factory_admin import router


class SecurityFixTests(unittest.TestCase):
    def test_factory_sections_have_explicit_permissions(self):
        expected = {
            "bots": "bots",
            "owners": "owners",
            "stats": "stats",
            "bcast": "broadcast",
            "blocks": "blocks",
            "sub": "subscriptions",
            "backup": "backups",
            "dbtools": "dbtools",
            "settings": "settings",
            "system": "system_settings",
            "logs": "logs",
            "admins": "admins",
        }
        for section, permission in expected.items():
            self.assertEqual(router._permission_for_action(section), permission)

    def test_factory_subscription_mutations_are_scoped_to_factory_bot(self):
        source = inspect.getsource(router.handle_callback)
        self.assertIn("UPDATE subscriptions SET active = NOT active WHERE id = ? AND bot_id = ?", source)
        self.assertIn("DELETE FROM subscriptions WHERE id = ? AND bot_id = ?", source)

    def test_verification_buttons_are_bound_to_recipient(self):
        user_id = 12345
        self.assertTrue(keyboards.verify_direct_kb(user_id)["inline_keyboard"][0][0]["callback_data"].endswith(f":{user_id}"))
        self.assertTrue(keyboards.verify_visit_kb("https://example.com", user_id)["inline_keyboard"][1][0]["callback_data"].endswith(f":{user_id}"))
        self.assertTrue(keyboards.verify_manual_pending_kb(user_id)["inline_keyboard"][0][0]["callback_data"].endswith(f":{user_id}"))
        check_data = keyboards.sub_gate_kb(["@channel"], user_id=user_id)["inline_keyboard"][-1][0]["callback_data"]
        self.assertEqual(check_data, f"chk:sub:{user_id}")


if __name__ == "__main__":
    unittest.main()