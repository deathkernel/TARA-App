import unittest
from tara_app.coding_sandbox_policy import SandboxCapabilities, may_execute

class SandboxPolicyTests(unittest.TestCase):
    def test_unisolated_execution_is_denied(self):
        self.assertFalse(may_execute(SandboxCapabilities(), user_approved=True))

    def test_isolation_and_approval_required(self):
        caps = SandboxCapabilities(isolated=True)
        self.assertFalse(may_execute(caps, user_approved=False))
        self.assertTrue(may_execute(caps, user_approved=True))

    def test_network_is_denied_unless_explicitly_enabled(self):
        caps = SandboxCapabilities(isolated=True)
        self.assertFalse(may_execute(caps, user_approved=True, requires_network=True))
        enabled = SandboxCapabilities(isolated=True, network_enabled=True)
        self.assertTrue(may_execute(enabled, user_approved=True, requires_network=True))

    def test_write_is_denied_unless_explicitly_enabled(self):
        caps = SandboxCapabilities(isolated=True)
        self.assertFalse(may_execute(caps, user_approved=True, requires_write=True))
        enabled = SandboxCapabilities(isolated=True, write_enabled=True)
        self.assertTrue(may_execute(enabled, user_approved=True, requires_write=True))

    def test_capability_flags_must_be_booleans(self):
        with self.assertRaises(ValueError):
            SandboxCapabilities(isolated=1)

    def test_bounds_are_validated(self):
        with self.assertRaises(ValueError):
            SandboxCapabilities(max_seconds=0)

if __name__ == "__main__":
    unittest.main()
