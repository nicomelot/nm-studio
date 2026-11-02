import unittest

from nm_bridge.recognition import review_suggestions


class RecognitionTests(unittest.TestCase):
    def test_matching_dpt_is_evidence_not_approval(self):
        addresses = [
            {"address": "1/1/0", "dpt": "DPST-1-1", "linked": True, "connections": []},
            {"address": "1/1/4", "dpt": "DPST-1-1", "linked": True, "connections": []},
        ]
        reviews = review_suggestions(addresses, [{"name": "L1", "kind": "light",
            "command": "1/1/0", "feedback": "1/1/4"}])
        self.assertEqual(reviews[0]["confidence"], "alta")
        self.assertTrue(reviews[0]["installer_confirmation_required"])
        self.assertFalse(reviews[0]["questions"])

    def test_unknown_dpt_requires_questions(self):
        addresses = [{"address": "1/0/1", "dpt": "", "linked": True,
                      "connections": [{"size": "1 Bit"}]}]
        reviews = review_suggestions(addresses, [{"name": "Dimmer L11", "kind": "dimmer",
            "command": "1/0/1", "brightness": "1/0/6"}])
        self.assertEqual(reviews[0]["confidence"], "bassa")
        self.assertTrue(any("1/0/6" in question for question in reviews[0]["questions"]))

    def test_dpt_conflict_never_marked_high(self):
        addresses = [{"address": "2/1/0", "dpt": "DPT-5.001", "linked": True, "connections": []}]
        reviews = review_suggestions(addresses, [{"name": "Sala", "kind": "climate",
             "command": "2/1/0"}])
        self.assertEqual(reviews[0]["confidence"], "bassa")
        self.assertTrue(any(c["status"] == "conflict_dpt" for c in reviews[0]["checks"]))


if __name__ == "__main__":
    unittest.main()
