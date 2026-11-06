"""Run with: python -m unittest discover -s tests -p test_record_dataset.py"""
import csv
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from modules.NiDAQ_controller import NiDAQJoysticks, OutputFormat
from record_dataset import make_labels


class AcquisitionTests(unittest.TestCase):
    def test_preserve_samples_does_not_discard_backlog(self):
        joystick = NiDAQJoysticks.__new__(NiDAQJoysticks)
        joystick.output_format = OutputFormat.FLOAT
        joystick.deadzone = joystick.padding = 0
        joystick.sample_rate = 60
        joystick.samples_read = 0
        joystick.ai_buffers = {}
        joystick.task_ai = SimpleNamespace(in_stream=SimpleNamespace(avail_samp_per_chan=3))
        joystick.task_di = SimpleNamespace(read=lambda: [False] * 12)
        counts = []

        def read(buffer, number_of_samples_per_channel):
            counts.append(number_of_samples_per_channel)
            buffer[:] = np.arange(number_of_samples_per_channel) + 2
            return number_of_samples_per_channel

        joystick.ai_reader = SimpleNamespace(read_many_sample=read)
        joystick.read(preserve_samples=True)
        self.assertEqual(joystick.samples_read, 1)
        self.assertEqual(joystick.last_raw_ai, [2] * 8)
        # Existing controller callers still drain backlog and return newest.
        joystick.read()
        self.assertEqual(counts, [1, 3])
        self.assertEqual(joystick.samples_read, 4)
        self.assertEqual(joystick.last_raw_ai, [4] * 8)

    def test_labels_apply_latency_and_reject_missing_coverage(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            with (folder / "axes.csv").open("w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["sample", "sample_est_ns", *[f"axis{i}" for i in range(8)]])
                writer.writerows([[0, 0, *([0] * 8)], [1, 16_000_000, *([1] * 8)], [2, 100_000_000, *([0] * 8)]])
            with (folder / "frames.csv").open("w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["frame", "segment", "delivery_ns"])
                writer.writerows([[0, 1, 18_000_000], [1, 1, 0], [2, 2, 60_000_000], [3, 2, 200_000_000]])
            make_labels(folder, latency_ms=10)
            with (folder / "labels.csv").open(newline="") as f:
                rows = list(csv.DictReader(f))
            self.assertEqual(rows[0]["exposure_est_ns"], "8000000")
            self.assertEqual(rows[0]["valid"], "1")
            self.assertAlmostEqual(float(rows[0]["axis0"]), 0.5)
            self.assertEqual([r["valid"] for r in rows[1:]], ["0", "0", "0"])


if __name__ == "__main__":
    unittest.main()
