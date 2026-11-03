"""Unit tests for explicit capability permission decisions."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from tara_app.permissions import PermissionAction, PermissionPolicy  # noqa: E402


class PermissionPolicyTests(unittest.TestCase):
    def test_unknown_capability_is_denied_by_default(self):
        result = PermissionPolicy().evaluate("chat")
        self.assertEqual(result.action, PermissionAction.DENY)

    def test_allowlisted_capability_is_allowed(self):
        policy = PermissionPolicy.from_iterables(allowed_capabilities=["chat"])
        self.assertEqual(policy.evaluate("chat").action, PermissionAction.ALLOW)

    def test_approval_gated_capability_requires_explicit_approval(self):
        policy = PermissionPolicy.from_iterables(
            allowed_capabilities=["code.apply_patch"], approval_required=["code.apply_patch"]
        )
        self.assertEqual(policy.evaluate("code.apply_patch").action, PermissionAction.REQUIRE_APPROVAL)
        self.assertEqual(policy.evaluate("code.apply_patch", approved=True).action, PermissionAction.ALLOW)

    def test_dangerous_capabilities_remain_denied_even_if_allowlisted(self):
        policy = PermissionPolicy.from_iterables(allowed_capabilities=["shell", "auto_merge"])
        self.assertEqual(policy.evaluate("shell").action, PermissionAction.DENY)
        self.assertEqual(policy.evaluate("auto_merge").action, PermissionAction.DENY)

    def test_blank_capability_is_denied(self):
        self.assertEqual(PermissionPolicy().evaluate(" ").action, PermissionAction.DENY)


if __name__ == "__main__":
    unittest.main()
