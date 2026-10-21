import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from natural_yield_estimator import stratify_terrain_panel


class NaturalYieldEstimatorTests(unittest.TestCase):
    def setUp(self):
        self.population = [
            dict(id="a", source_membership=["A"], outcome=1),
            dict(id="b", source_membership=["B"], outcome=2),
            dict(id="ab", source_membership=["A", "B"], outcome=4),
            dict(id="outside", source_membership=[], outcome=8),
        ]
        self.cohorts = {
            name: [r for r in self.population if name in r["source_membership"]]
            for name in ["A", "B"]
        }

    def test_overlapping_cohorts_recover_population_mean(self):
        for order in [["A", "B"], ["B", "A"]]:
            cohorts = {name: self.cohorts[name] for name in order}
            rows, counts = stratify_terrain_panel(self.population, cohorts, 4)
            self.assertEqual(counts, {"A": 2, "B": 2})
            self.assertEqual(len(rows), 4)
            self.assertEqual(
                sum(r["trial_weight"] * r["outcome"] for r in rows), 15 / 4
            )

    def test_repeating_a_conditional_cohort_preserves_estimate(self):
        cohorts = {name: rows * 7 for name, rows in self.cohorts.items()}
        rows, _ = stratify_terrain_panel(self.population, cohorts, 4)
        self.assertAlmostEqual(
            sum(r["trial_weight"] * r["outcome"] for r in rows), 15 / 4
        )

    def test_rejected_full_trials_stay_in_denominator(self):
        rows, _ = stratify_terrain_panel(self.population, self.cohorts, 8)
        self.assertEqual(sum(r["trial_weight"] * r["outcome"] for r in rows), 15 / 8)


if __name__ == "__main__":
    unittest.main()
