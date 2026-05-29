"""Tests for the employee task reminder cron (AIQ-76 / AIQ-34-D)."""
import unittest
from unittest.mock import patch

from backend.app.services import employee_task_reminders as etr


def _row(**kw):
    base = {
        "task_id": "t1",
        "title": "Upload passport",
        "case_id": "case-1",
        "employee_id": "emp-1",
        "employee_name": "Ada Lovelace",
        "employee_email": "ada@example.com",
        "hr_owner_id": None,
        "hr_name": None,
        "hr_email": None,
    }
    base.update(kw)
    return base


class TestProcessWindow(unittest.TestCase):
    @patch.object(etr, "_stamp")
    @patch.object(etr, "_inapp")
    @patch.object(etr, "_send_email")
    @patch.object(etr, "_fetch_due_tasks")
    def test_d7_sends_email_and_stamps(self, fetch, send, inapp, stamp):
        fetch.return_value = [_row()]
        res = etr._process_window("d7", 7, "reminded_d7_at")

        self.assertEqual(res, {"checked": 1, "reminded": 1, "errors": 0})
        send.assert_called_once()
        # Dedup: the processed task is stamped so the next run won't re-fetch it.
        stamp.assert_called_once_with(["t1"], "reminded_d7_at")
        inapp.assert_not_called()  # d7 is email-only

    @patch.object(etr, "_stamp")
    @patch.object(etr, "_send_email")
    @patch.object(etr, "_fetch_due_tasks")
    def test_d3_email_includes_task_names(self, fetch, send, stamp):
        fetch.return_value = [
            _row(task_id="t1", title="Upload passport"),
            _row(task_id="t2", title="Sign lease"),
        ]
        etr._process_window("d3", 3, "reminded_d3_at")

        send.assert_called_once()
        titles = send.call_args.kwargs["task_titles"]
        self.assertEqual(set(titles), {"Upload passport", "Sign lease"})

    @patch.object(etr, "_stamp")
    @patch.object(etr, "_send_email")
    @patch.object(etr, "_fetch_due_tasks")
    def test_groups_by_employee_into_one_email(self, fetch, send, stamp):
        fetch.return_value = [
            _row(task_id="t1", title="A"),
            _row(task_id="t2", title="B"),
        ]
        res = etr._process_window("d7", 7, "reminded_d7_at")

        self.assertEqual(res["reminded"], 2)
        send.assert_called_once()  # one consolidated email
        stamp.assert_called_once_with(["t1", "t2"], "reminded_d7_at")

    @patch.object(etr, "_stamp")
    @patch.object(etr, "_inapp")
    @patch.object(etr, "_send_email")
    @patch.object(etr, "_fetch_due_tasks")
    def test_d0_notifies_employee_and_hr(self, fetch, send, inapp, stamp):
        fetch.return_value = [
            _row(hr_owner_id="hr-1", hr_name="Grace Hopper", hr_email="grace@example.com")
        ]
        etr._process_window("d0", 0, "reminded_d0_at")

        # Two emails: employee + HR.
        self.assertEqual(send.call_count, 2)
        recipients = {c.kwargs["to"] for c in send.call_args_list}
        self.assertEqual(recipients, {"ada@example.com", "grace@example.com"})
        # Two in-app notifications: employee d0 + HR d0.
        types = {c.args[1] for c in inapp.call_args_list}
        self.assertEqual(types, {"task.reminder_d0", "task.reminder_hr_d0"})

    @patch.object(etr, "_stamp")
    @patch.object(etr, "_inapp")
    @patch.object(etr, "_send_email")
    @patch.object(etr, "_fetch_due_tasks")
    def test_d0_without_hr_owner_only_emails_employee(self, fetch, send, inapp, stamp):
        fetch.return_value = [_row(hr_owner_id=None)]
        etr._process_window("d0", 0, "reminded_d0_at")

        send.assert_called_once()
        # Only the employee in-app notification fires.
        types = {c.args[1] for c in inapp.call_args_list}
        self.assertEqual(types, {"task.reminder_d0"})

    @patch.object(etr, "_stamp")
    @patch.object(etr, "_send_email")
    @patch.object(etr, "_fetch_due_tasks")
    def test_missing_email_still_stamps(self, fetch, send, stamp):
        # No employee_email: don't send, but stamp so the cron doesn't retry forever.
        fetch.return_value = [_row(employee_email=None)]
        res = etr._process_window("d7", 7, "reminded_d7_at")

        send.assert_not_called()
        stamp.assert_called_once_with(["t1"], "reminded_d7_at")
        self.assertEqual(res["reminded"], 1)

    @patch.object(etr, "_fetch_due_tasks")
    def test_query_failure_is_contained(self, fetch):
        fetch.side_effect = RuntimeError("db down")
        res = etr._process_window("d7", 7, "reminded_d7_at")
        self.assertEqual(res, {"checked": 0, "reminded": 0, "errors": 1})


class TestRunTaskReminderCron(unittest.TestCase):
    @patch.object(etr, "_process_window")
    def test_runs_all_three_windows_and_rolls_up(self, proc):
        proc.return_value = {"checked": 2, "reminded": 2, "errors": 0}
        out = etr.run_task_reminder_cron()

        self.assertEqual(proc.call_count, 3)
        kinds = {c.args[0] for c in proc.call_args_list}
        self.assertEqual(kinds, {"d7", "d3", "d0"})
        self.assertEqual(out["totals"], {"checked": 6, "reminded": 6, "errors": 0})


if __name__ == "__main__":
    unittest.main()
