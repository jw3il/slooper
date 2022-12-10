import numpy as np


class ValueStats:
    """
    Insert values into a ring and get aggregated statistics.
    """

    def __init__(self, capacity, dtype):
        self.data = np.empty(capacity, dtype=dtype)
        self.count = 0
        self.idx = 0

    def insert(self, value):
        self.data[self.idx] = value
        self.idx = (self.idx + 1) % self.data.shape[0]
        self.count = min(self.count + 1, self.data.shape[0])

    def get_stats(self):
        if self.count == 0:
            return {
                "mean": 0,
                "max": 0,
                "std": 0,
                "99p": 0,
            }

        return {
            "mean": self.data[: self.count].mean().item(),
            "max": self.data[: self.count].max().item(),
            "std": self.data[: self.count].std().item(),
            "99p": np.percentile(self.data[: self.count], 99).item(),
        }
