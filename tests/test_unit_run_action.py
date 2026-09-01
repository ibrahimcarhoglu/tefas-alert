import unittest
from unittest.mock import patch

import run_action


class RunActionResilienceTests(unittest.TestCase):
    @patch("run_action.fetch_range_and_store")
    @patch("run_action._signal_history_day_count")
    def test_missing_signal_history_is_backfilled(self, day_count, fetch_range):
        day_count.side_effect = [40, 280]

        ready = run_action.ensure_signal_history("2026-08-31")

        self.assertTrue(ready)
        fetch_range.assert_called_once_with("2025-06-27", "2026-08-31")

    @patch("run_action.fetch_range_and_store", side_effect=RuntimeError("network"))
    @patch("run_action._signal_history_day_count", return_value=40)
    def test_backfill_failure_does_not_claim_rotation_is_ready(self, _day_count, _fetch_range):
        self.assertFalse(run_action.ensure_signal_history("2026-08-31"))

    def test_safe_notification_failure_does_not_escape(self):
        result = run_action._safely("test", lambda: (_ for _ in ()).throw(RuntimeError("boom")))
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
