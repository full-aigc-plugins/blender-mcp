"""Local approval for gated commands: minting, binding, single use, and expiry.

These tests exercise the Session security boundary without Blender: dispatch is a
recording stub, so every assertion is about the Harness contract itself.
"""

import sys
import time
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from partme_blender_mcp.harness.errors import HarnessError  # noqa: E402
from partme_blender_mcp.harness.execution_policy import ExecutionPolicy  # noqa: E402
from partme_blender_mcp.harness.session import HarnessSession  # noqa: E402


class SessionFixture:
    def __init__(self):
        self.calls = []
        self.session = HarnessSession("approval-session", dispatch=self.dispatch)

    def dispatch(self, command, arguments):
        self.calls.append((command, arguments))
        return {"changedObjects": ["Cube"] if command == "object.delete" else []}

    def call(self, request_id, command, arguments, *, authorization=None, revision=None):
        payload = {
            "protocolVersion": "codex-blender/v1",
            "sessionId": "approval-session",
            "requestId": request_id,
            "transactionId": "tx-" + request_id,
            "command": command,
            "arguments": arguments,
        }
        if revision is not None:
            payload["expectedSceneRevision"] = revision
        if authorization is not None:
            payload["authorization"] = authorization
        response = self.session.handle(payload)
        return response.get("error", {}).get("code") or response.get("status")

    @property
    def revision(self):
        return self.session.scene_revision


class DenialAndPendingTests(unittest.TestCase):
    def test_provider_staging_is_denied_before_resolver_dispatch(self):
        fixture = SessionFixture()
        self.assertEqual(fixture.call('stage', 'asset.fetch_generated',
            {'providerId': 'hyper3d', 'params': {'task_uuid': 'job'}}, revision=0),
            'AUTHORIZATION_REQUIRED')
        self.assertEqual(fixture.calls, [])
        fixture.session.approve_pending('stage')
        self.assertEqual(fixture.call('stage', 'asset.fetch_generated',
            {'providerId': 'hyper3d', 'params': {'task_uuid': 'job'}}, revision=0), 'succeeded')
        self.assertEqual(fixture.calls, [('asset.fetch_generated',
            {'providerId': 'hyper3d', 'params': {'task_uuid': 'job'}})])

    def test_gated_command_without_approval_is_refused_and_listed(self):
        fixture = SessionFixture()
        self.assertEqual(
            fixture.call("r1", "object.delete", {"name": "Cube"}, revision=0), "AUTHORIZATION_REQUIRED"
        )
        self.assertEqual(fixture.calls, [], "a refused command must not reach dispatch")
        pending = fixture.session.pending_authorizations()
        self.assertEqual([entry["requestId"] for entry in pending], ["r1"])
        self.assertEqual(pending[0]["command"], "object.delete")
        self.assertIn("name=Cube", pending[0]["summary"])

    def test_pending_summary_hides_envelope_fields(self):
        fixture = SessionFixture()
        fixture.call("r1", "object.delete", {"name": "Cube", "_authorization": "secret"}, revision=0)
        summary = fixture.session.pending_authorizations()[0]["summary"]
        self.assertNotIn("secret", summary)
        self.assertNotIn("_authorization", summary)

    def test_read_only_commands_never_need_approval(self):
        fixture = SessionFixture()
        self.assertEqual(fixture.call("r1", "scene.inspect", {}), "succeeded")
        self.assertEqual(fixture.session.pending_authorizations(), [])

    def test_auto_asset_policy_runs_enabled_provider_generation_without_approval_card(self):
        calls = []
        policy = ExecutionPolicy.from_dict({
            "mode": "auto_with_budget",
            "approvedOutputRoot": str((ROOT / ".tmp/partme-output").resolve()),
            "assetStrategy": "auto_search_generate",
        })
        session = HarnessSession(
            "approval-session",
            dispatch=lambda command, arguments: calls.append((command, arguments)) or {
                "changedObjects": [], "result": {"approved": True},
            },
            execution_policy=policy,
        )
        fixture = SessionFixture()
        fixture.session = session

        result = fixture.call(
            "provider-auto", "provider.external_action",
            {"providerId": "hunyuan3d", "action": "generate", "risk": "paid_generation"},
            revision=0,
        )

        self.assertEqual(result, "succeeded")
        self.assertEqual(session.pending_authorizations(), [])
        self.assertEqual(calls[0][0], "provider.external_action")
        self.assertEqual(session.scene_revision, 0, "a provider gate must not pretend the Blender scene changed")

    def test_paid_generation_over_cumulative_budget_requires_local_approval(self):
        calls = []
        policy = ExecutionPolicy.from_dict({
            "mode": "auto_with_budget",
            "approvedOutputRoot": str((ROOT / ".tmp/partme-output").resolve()),
            "assetStrategy": "auto_search_generate",
            "downstreamBudgetLimit": "5.00",
        })
        session = HarnessSession(
            "approval-session",
            dispatch=lambda command, arguments: calls.append((command, arguments)) or {
                "changedObjects": [], "result": {"approved": True},
            },
            execution_policy=policy,
        )
        fixture = SessionFixture()
        fixture.session = session

        first = fixture.call(
            "provider-budget-1", "provider.external_action",
            {"providerId": "hunyuan3d", "action": "generate", "risk": "paid_generation",
             "estimatedCost": "3.00"}, revision=0,
        )
        second = fixture.call(
            "provider-budget-2", "provider.external_action",
            {"providerId": "hunyuan3d", "action": "generate", "risk": "paid_generation",
             "estimatedCost": "3.00"}, revision=0,
        )

        self.assertEqual(first, "succeeded")
        self.assertEqual(second, "AUTHORIZATION_REQUIRED")
        self.assertEqual(len(calls), 1)
        self.assertEqual(session.status()["downstreamBudgetSpent"], "3.00")
        pending = session.pending_authorizations()[0]
        self.assertEqual(pending["requestId"], "provider-budget-2")
        self.assertIn("estimatedCost=3.00", pending["summary"])

    def test_configured_budget_requires_an_estimate_before_automatic_generation(self):
        policy = ExecutionPolicy.from_dict({
            "mode": "auto_with_budget",
            "approvedOutputRoot": str((ROOT / ".tmp/partme-output").resolve()),
            "assetStrategy": "auto_search_generate",
            "downstreamBudgetLimit": "5.00",
        })
        fixture = SessionFixture()
        fixture.session = HarnessSession(
            "approval-session", dispatch=fixture.dispatch, execution_policy=policy,
        )

        result = fixture.call(
            "provider-unknown-cost", "provider.external_action",
            {"providerId": "hyper3d", "action": "generate", "risk": "paid_generation"}, revision=0,
        )

        self.assertEqual(result, "AUTHORIZATION_REQUIRED")
        self.assertEqual(fixture.calls, [])

    def test_interactive_provider_generation_still_requires_local_approval(self):
        fixture = SessionFixture()

        result = fixture.call(
            "provider-review", "provider.external_action",
            {"providerId": "hunyuan3d", "action": "generate", "risk": "paid_generation"},
            revision=0,
        )

        self.assertEqual(result, "AUTHORIZATION_REQUIRED")
        self.assertEqual(fixture.session.pending_authorizations()[0]["requestId"], "provider-review")

    def test_retry_before_approval_stays_refused(self):
        fixture = SessionFixture()
        fixture.call("r1", "object.delete", {"name": "Cube"}, revision=0)
        self.assertEqual(
            fixture.call("r1", "object.delete", {"name": "Cube"}, revision=0), "AUTHORIZATION_REQUIRED"
        )
        self.assertEqual(fixture.calls, [])


class ApprovalTests(unittest.TestCase):
    def test_approved_request_succeeds_on_retry_with_same_id(self):
        fixture = SessionFixture()
        fixture.call("r1", "object.delete", {"name": "Cube"}, revision=0)
        result = fixture.session.approve_pending("r1")
        self.assertEqual(result, {"requestId": "r1", "command": "object.delete", "ttlSeconds": 120})
        self.assertEqual(fixture.call("r1", "object.delete", {"name": "Cube"}, revision=0), "succeeded")
        self.assertEqual([command for command, _ in fixture.calls], ["object.delete"])

    def test_replay_of_approved_request_does_not_repeat_the_side_effect(self):
        fixture = SessionFixture()
        fixture.call("r1", "object.delete", {"name": "Cube"}, revision=0)
        fixture.session.approve_pending("r1")
        fixture.call("r1", "object.delete", {"name": "Cube"}, revision=0)
        self.assertEqual(fixture.call("r1", "object.delete", {"name": "Cube"}, revision=0), "succeeded")
        self.assertEqual(len(fixture.calls), 1, "same request id must replay, not re-execute")

    def test_approval_is_bound_to_the_request_id(self):
        fixture = SessionFixture()
        fixture.call("r1", "object.delete", {"name": "Cube"}, revision=0)
        fixture.session.approve_pending("r1")
        self.assertEqual(
            fixture.call("r2", "object.delete", {"name": "Cube"}, revision=0), "AUTHORIZATION_REQUIRED"
        )
        self.assertEqual(fixture.calls, [])

    def test_approval_is_bound_to_the_command(self):
        fixture = SessionFixture()
        fixture.call("r1", "object.delete", {"name": "Cube"}, revision=0)
        fixture.session.approve_pending("r1")
        self.assertEqual(fixture.call("r1", "export.final", {}, revision=0), "AUTHORIZATION_REQUIRED")
        self.assertEqual(fixture.calls, [])

    def test_approval_is_single_use_for_a_new_request(self):
        fixture = SessionFixture()
        fixture.call("r1", "object.delete", {"name": "Cube"}, revision=0)
        fixture.session.approve_pending("r1")
        fixture.call("r1", "object.delete", {"name": "Cube"}, revision=0)
        self.assertEqual(
            fixture.call("r2", "object.delete", {"name": "Cube"}, revision=fixture.revision),
            "AUTHORIZATION_REQUIRED",
        )
        self.assertEqual(len(fixture.calls), 1)

    def test_expired_approval_is_refused(self):
        fixture = SessionFixture()
        fixture.call("r1", "object.delete", {"name": "Cube"}, revision=0)
        fixture.session.approve_pending("r1", ttl_seconds=1)
        time.sleep(1.1)
        self.assertEqual(
            fixture.call("r1", "object.delete", {"name": "Cube"}, revision=0), "AUTHORIZATION_REQUIRED"
        )
        self.assertEqual(fixture.calls, [])

    def test_ttl_is_clamped_to_the_documented_maximum(self):
        fixture = SessionFixture()
        fixture.call("r1", "object.delete", {"name": "Cube"}, revision=0)
        self.assertEqual(fixture.session.approve_pending("r1", ttl_seconds=99999)["ttlSeconds"], 300)

    def test_unknown_request_id_cannot_be_approved(self):
        fixture = SessionFixture()
        with self.assertRaises(HarnessError) as context:
            fixture.session.approve_pending("never-seen")
        self.assertEqual(context.exception.code, "UNKNOWN_PENDING_AUTHORIZATION")

    def test_pending_list_is_bounded(self):
        fixture = SessionFixture()
        for index in range(15):
            fixture.call(f"r{index}", "object.delete", {"name": "Cube"}, revision=0)
        self.assertEqual(len(fixture.session.pending_authorizations()), 10)
        self.assertEqual(
            fixture.session.pending_authorizations()[-1]["requestId"], "r14", "newest entries are kept"
        )


class DenyTests(unittest.TestCase):
    def test_denied_request_stops_asking_the_user_again(self):
        fixture = SessionFixture()
        fixture.call("r1", "object.delete", {"name": "Cube"}, revision=0)
        fixture.session.deny_pending("r1")
        self.assertEqual(fixture.session.pending_authorizations(), [])
        fixture.call("r1", "object.delete", {"name": "Cube"}, revision=0)
        self.assertEqual(fixture.session.pending_authorizations(), [], "a denial must not re-prompt")
        self.assertEqual(fixture.calls, [])

    def test_a_new_request_id_can_ask_again_after_a_denial(self):
        fixture = SessionFixture()
        fixture.call("r1", "object.delete", {"name": "Cube"}, revision=0)
        fixture.session.deny_pending("r1")
        fixture.call("r2", "object.delete", {"name": "Cube"}, revision=0)
        self.assertEqual([entry["requestId"] for entry in fixture.session.pending_authorizations()], ["r2"])


class BoundaryTests(unittest.TestCase):
    def test_client_supplied_transport_claim_still_works(self):
        """The host approval bridge path keeps working alongside local approval."""
        fixture = SessionFixture()
        fixture.call("r1", "object.delete", {"name": "Cube"}, revision=0)
        issued = fixture.session.handle({
            "protocolVersion": "codex-blender/v1", "sessionId": "approval-session", "requestId": "a1",
            "transactionId": "tx-a1", "command": "session.authorize",
            "arguments": {"action": "object.delete", "requestId": "r1", "userConfirmed": True},
        })
        claim = issued["result"]["authorization"]
        self.assertEqual(
            fixture.call("r1", "object.delete", {"name": "Cube"}, authorization=claim, revision=0), "succeeded"
        )

    def test_claim_for_another_request_id_is_not_reusable(self):
        fixture = SessionFixture()
        fixture.call("r1", "object.delete", {"name": "Cube"}, revision=0)
        issued = fixture.session.handle({
            "protocolVersion": "codex-blender/v1", "sessionId": "approval-session", "requestId": "a1",
            "transactionId": "tx-a1", "command": "session.authorize",
            "arguments": {"action": "object.delete", "requestId": "r1", "userConfirmed": True},
        })
        claim = issued["result"]["authorization"]
        self.assertEqual(
            fixture.call("r9", "object.delete", {"name": "Cube"}, authorization=claim, revision=0),
            "AUTHORIZATION_REQUIRED",
        )

    def test_revoke_clears_pending_and_approvals(self):
        fixture = SessionFixture()
        fixture.call("r1", "object.delete", {"name": "Cube"}, revision=0)
        fixture.session.approve_pending("r1")
        fixture.session.revoke()
        self.assertEqual(fixture.session.pending_authorizations(), [])
        self.assertTrue(fixture.session.status()["revoked"])

    def test_user_takeover_invalidates_outstanding_approvals(self):
        fixture = SessionFixture()
        fixture.call("r1", "object.delete", {"name": "Cube"}, revision=0)
        fixture.session.approve_pending("r1")
        fixture.session.pause()
        self.assertEqual(
            fixture.call("r1", "object.delete", {"name": "Cube"}, revision=0), "SESSION_PAUSED"
        )
        self.assertEqual(fixture.calls, [])

    def test_status_reports_pending_authorizations(self):
        fixture = SessionFixture()
        self.assertEqual(fixture.session.status()["pendingAuthorizations"], 0)
        fixture.call("r1", "object.delete", {"name": "Cube"}, revision=0)
        self.assertEqual(fixture.session.status()["pendingAuthorizations"], 1)

    def test_approval_and_use_are_audited(self):
        fixture = SessionFixture()
        fixture.call("r1", "object.delete", {"name": "Cube"}, revision=0)
        fixture.session.approve_pending("r1")
        fixture.call("r1", "object.delete", {"name": "Cube"}, revision=0)
        marks = [entry.get("authorization") for entry in fixture.session.audit_entries()]
        self.assertIn("approved_locally", marks)
        self.assertIn("used_local_approval", marks)


if __name__ == "__main__":
    unittest.main()
