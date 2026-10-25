import unittest
from contracts import public_evidence, plan_digest, require_approved_plan, observe_loaded_configuration


class ContractsTest(unittest.TestCase):
    def test_nested_private_context_is_removed_without_losing_receipts(self):
        raw = {"actions": [{"result": {"journal": {"adapter_context": {"path": "/private"}, "status": "SUCCEEDED"}}}], "adapter_context": {}, "receipt": {"id": "original"}}
        self.assertEqual(public_evidence(raw), {"actions": [{"result": {"journal": {"status": "SUCCEEDED"}}}], "receipt": {"id": "original"}})

    def test_altered_native_plan_or_payload_is_refused(self):
        payload = {"path": "document.txt", "content": "reviewed"}
        record = {"payload": payload, "plan": {"tree": {"children": [{"payload": {"literal": dict(payload)}}]}}}
        approved = plan_digest(record["plan"])
        require_approved_plan(record, approved)
        record["plan"]["tree"]["children"][0]["payload"]["literal"]["content"] = "altered"
        with self.assertRaises(ValueError):
            require_approved_plan(record, approved)
        with self.assertRaises(ValueError):
            require_approved_plan(record, plan_digest(record["plan"]))

    def test_reload_lag_retains_both_responses(self):
        replies = iter([(503, {"configurationSha256": "old"}, 1), (200, {"configurationSha256": "reviewed"}, 2)])
        status, _, attempts = observe_loaded_configuration(lambda: next(replies), "reviewed")
        self.assertEqual(status, 200)
        self.assertEqual([a["httpStatus"] for a in attempts], [503, 200])

    def test_matching_maintenance_response_is_not_retried_away(self):
        status, _, attempts = observe_loaded_configuration(lambda: (503, {"configurationSha256": "reviewed"}, 1), "reviewed")
        self.assertEqual(status, 503)
        self.assertEqual(len(attempts), 1)

    def test_unloaded_configuration_has_bounded_observation(self):
        status, _, attempts = observe_loaded_configuration(lambda: (503, {"configurationSha256": "old"}, 1), "reviewed", timeout=0)
        self.assertEqual(status, 503)
        self.assertEqual(len(attempts), 1)


if __name__ == "__main__":
    unittest.main()
