import unittest

import numpy as np
import pandas as pd

from src.analysis.ff5.core import StrategyEngine, run_ols


class TestFF5(unittest.TestCase):
    def test_ols(self):
        X = np.column_stack([np.ones(10), np.arange(10)])
        y = 2 * X[:, 1] + 1
        np.testing.assert_allclose(run_ols(X, y)["beta"], [1, 2], atol=1e-10)

    def test_prep(self):
        d = pd.date_range("2023-01-01", periods=1, freq="ME")
        s = pd.DataFrame({"strategy_return": [0.1]}, index=d)
        f = pd.DataFrame({"mkt_rf": [0.05], "smb": [0], "hml": [0], "rmw": [0], "cma": [0], "rf": [0.02]}, index=d)
        _, y, _ = StrategyEngine().prepare(s, f)
        self.assertAlmostEqual(y[0], 0.08)


if __name__ == "__main__":
    unittest.main()
