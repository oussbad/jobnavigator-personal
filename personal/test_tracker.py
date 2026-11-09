import unittest
from personal.tracker import normalize

class TrackerTests(unittest.TestCase):
    def test_only_confirmed_sends_import_and_duplicates_do_not_repeat(self):
        def row(status, suffix):
            return dict(company="Example", role="Engineer", url="https://example.test/" + suffix, status=status)
        records = [row("Submitted successfully; confirmed on employer site", "1"),
                   row("Submitted successfully; confirmed on employer site", "1"),
                   row("Application sent by email; Gmail Sent verified", "2"),
                   row("Completed; Not submitted; employer server rejected", "3"),
                   row("CV uploaded; pending submission", "4"),
                   row("Submitted; unconfirmed", "5")]
        confirmed, pending = normalize({"applications": records})
        self.assertEqual(len(confirmed), 2)
        self.assertEqual(len(pending), 3)

    def test_incomplete_records_are_preserved_as_pending(self):
        confirmed, pending = normalize({"applications": [{"status": "Submitted"}]})
        self.assertEqual(confirmed, [])
        self.assertEqual(len(pending), 1)

if __name__ == "__main__":
    unittest.main()
