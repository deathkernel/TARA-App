import unittest
from tara_app.offline_evals import EvalCase, run_offline_evals

class OfflineEvalTests(unittest.TestCase):
    def test_exact_match_results_are_deterministic(self):
        cases = [EvalCase("one", "hello", "HELLO"), EvalCase("two", "world", "no")]
        results = run_offline_evals(cases, str.upper)
        self.assertEqual([(r.case_id, r.passed) for r in results], [("one", True), ("two", False)])

    def test_duplicate_ids_rejected(self):
        cases = [EvalCase("same", "a", "A"), EvalCase("same", "b", "B")]
        with self.assertRaises(ValueError): run_offline_evals(cases, str.upper)

if __name__ == "__main__": unittest.main()
