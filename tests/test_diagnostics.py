from __future__ import annotations

import unittest
from unittest.mock import patch

from tara_app.diagnostics import (
    check_omniroute_connectivity,
    collect_system_diagnostics,
    get_disk_metrics,
    get_windows_cpu_load,
    get_windows_memory,
)


class DiagnosticsTests(unittest.TestCase):
    def test_windows_memory(self):
        mem = get_windows_memory()
        self.assertIsInstance(mem, dict)
        if mem.get("supported"):
            self.assertGreater(mem["total_gb"], 0)
            self.assertGreaterEqual(mem["load_percent"], 0)
            self.assertLessEqual(mem["load_percent"], 100)

    def test_windows_cpu_load(self):
        cpu = get_windows_cpu_load(sample_ms=0.01)
        self.assertIsInstance(cpu, dict)
        if cpu.get("supported"):
            self.assertGreaterEqual(cpu["cpu_percent"], 0.0)
            self.assertLessEqual(cpu["cpu_percent"], 100.0)

    def test_disk_metrics(self):
        disk = get_disk_metrics()
        self.assertTrue(disk["supported"])
        self.assertGreater(disk["total_gb"], 0)
        self.assertGreaterEqual(disk["free_gb"], 0)

    def test_check_omniroute_connectivity_handles_offline(self):
        res = check_omniroute_connectivity(base_url="http://127.0.0.1:20128/v1", timeout=0.1)
        self.assertIn(res["status"], {"connected", "gateway_reachable", "unreachable"})

    def test_collect_system_diagnostics(self):
        diag = collect_system_diagnostics()
        self.assertIn(diag["overall_status"], {"GOOD", "NORMAL", "WARNING", "CRITICAL"})
        self.assertIn("hardware", diag)
        self.assertIn("omniroute", diag)
        self.assertIn("issues", diag)


if __name__ == "__main__":
    unittest.main()
