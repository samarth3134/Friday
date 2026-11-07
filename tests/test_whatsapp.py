"""Exercise actual WhatsApp code with fake desktop, process and clock modules."""
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch

from tests.support import load_module


class WhatsAppTests(unittest.TestCase):
    def setUp(self):
        self.keyboard = MagicMock(FAILSAFE=True)
        self.windows = MagicMock()
        self.process = MagicMock()
        self.clock = MagicMock()
        self.mod = load_module("whatsapp_desktop", {
            "pyautogui": self.keyboard,
            "pygetwindow": self.windows,
            "subprocess": self.process,
            "time": self.clock,
            "config": SimpleNamespace(WHATSAPP_SESSION_PATH="fixture-unused-session"),
        })

    def test_launch_dispatch_and_failure(self):
        self.assertTrue(self.mod._launch_whatsapp())
        self.process.Popen.assert_called_once_with(
            ["shell:AppsFolder\\5319275A.WhatsAppDesktop_cv1g1gvanyjgm!App"], shell=True)
        self.process.Popen.side_effect = OSError("fixture missing app")
        self.assertFalse(self.mod._launch_whatsapp())

    def test_find_visible_window_and_activate(self):
        hidden, visible = MagicMock(visible=False), MagicMock(visible=True)
        self.windows.getWindowsWithTitle.return_value = [hidden, visible]
        self.assertIs(self.mod._find_window(), visible)
        self.assertTrue(self.mod._activate())
        visible.activate.assert_called_once()
        visible.activate.side_effect = RuntimeError("fixture focus failure")
        self.assertFalse(self.mod._activate())

    def test_missing_window_bounded_poll(self):
        self.windows.getWindowsWithTitle.return_value = []
        self.assertIsNone(self.mod._find_window())
        self.assertEqual(self.windows.getWindowsWithTitle.call_count, 30)
        self.assertEqual(sum(args.args[0] for args in self.clock.sleep.call_args_list), 15)
        self.assertFalse(self.mod._activate())

    def test_readiness_success_launch_error_and_existing_error(self):
        self.windows.getWindowsWithTitle.return_value = [MagicMock(visible=True)]
        self.assertEqual(self.mod._ensure_whatsapp(), (True, None))
        self.assertTrue(self.mod._wa_ready)
        self.mod._wa_ready = False
        self.process.Popen.side_effect = OSError("fixture missing app")
        self.mod._start_whatsapp_client()
        ready, error = self.mod._ensure_whatsapp()
        self.assertIsNone(ready)
        self.assertIn("Could not launch", error)
        self.process.Popen.reset_mock()
        self.assertEqual(self.mod._ensure_whatsapp(), (None, error))
        self.process.Popen.assert_not_called()

    def test_regression_fresh_start_failure_reports_cause_immediately(self):
        self.process.Popen.side_effect = OSError("fixture missing app")
        ready, error = self.mod._ensure_whatsapp()
        self.assertIsNone(ready)
        self.assertIn("Could not launch", error)

    def test_read_and_unread_honestly_describe_limits(self):
        self.mod._wa_ready = True
        with patch.object(self.mod, "_activate", return_value=True):
            unread = self.mod.wa_get_unread()
            self.assertIn("cannot read it reliably", unread)
            self.keyboard.hotkey.assert_has_calls([
                call("ctrl", "1"), call("ctrl", "shift", "]"), call("ctrl", "shift", "[")])
            read = self.mod.wa_read_chat("Fixture Contact", n=3)
            self.assertIn("Reading messages via automation is limited", read)
            self.keyboard.write.assert_called_once_with("Fixture Contact")
            self.keyboard.press.assert_called_once_with("enter")

    def test_actions_return_readiness_and_activation_errors_without_typing(self):
        actions = [self.mod.wa_get_unread, lambda: self.mod.wa_read_chat("Fixture"),
                   lambda: self.mod.wa_send("Fixture", "Offline message")]
        for action in actions:
            with self.subTest(action=action):
                self.mod._wa_error = "fixture unavailable"
                self.assertEqual(action(), "fixture unavailable")
                self.mod._wa_error = None
                self.mod._wa_ready = True
                with patch.object(self.mod, "_activate", return_value=False):
                    self.assertEqual(action(), "Could not find WhatsApp window.")
        self.keyboard.write.assert_not_called()
        self.keyboard.hotkey.assert_not_called()
        self.keyboard.press.assert_not_called()

    def test_send_sequence_ascii_and_unicode_forwarding_only(self):
        # Only verifies arguments reach the mocked keyboard, not Unicode delivery.
        self.mod._wa_ready = True
        for message in ["Offline fixture", "Namaste \u0928\u092e\u0938\u094d\u0924\u0947 \U0001f642"]:
            with self.subTest(message=message), patch.object(self.mod, "_activate", return_value=True):
                self.keyboard.reset_mock()
                self.mod.wa_send("Fixture Contact", message)
                self.assertEqual(self.keyboard.method_calls, [
                    call.hotkey("ctrl", "n"), call.write("Fixture Contact"),
                    call.press("enter"), call.write(message), call.press("enter")])

    def test_start_creates_daemon_without_running_it(self):
        with patch.object(self.mod.threading, "Thread") as thread:
            self.mod._start()
        thread.assert_called_once_with(target=self.mod._start_whatsapp_client, daemon=True)
        thread.return_value.start.assert_called_once()
        self.process.Popen.assert_not_called()

    def test_regression_startup_timeout_matches_ten_second_claim(self):
        self.windows.getWindowsWithTitle.return_value = []
        self.mod._start_whatsapp_client()
        self.assertIn("10 seconds", self.mod._wa_error)
        logical_seconds = sum(args.args[0] for args in self.clock.sleep.call_args_list)
        self.assertLessEqual(logical_seconds, 10, "Nested polling actually sleeps 310 seconds")

    def test_regression_unverified_send_does_not_claim_confirmation(self):
        # All keyboard actions are no-ops and no recipient/delivery is verified.
        self.mod._wa_ready = True
        with patch.object(self.mod, "_activate", return_value=True):
            response = self.mod.wa_send("Unresolved Fixture Contact", "Offline fixture")
        self.assertNotIn("Sent your WhatsApp message", response,
                         "A successful keystroke sequence does not verify recipient or delivery")

    def test_regression_import_preserves_desktop_failsafe(self):
        self.assertTrue(self.keyboard.FAILSAFE,
                        "Importing WhatsApp must not disable the desktop automation failsafe globally")


if __name__ == "__main__":
    unittest.main()
