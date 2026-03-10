#!/usr/bin/env python3
"""Unit tests for runtime interface boundaries."""

import sys
import types
import unittest
from unittest import mock

from evoclaw.runtime import interfaces as runtime_interfaces
from evoclaw.runtime.interfaces import governance as governance_iface
from evoclaw.runtime.interfaces import passive_learning as passive_iface


class RuntimeInterfacesTests(unittest.TestCase):
    def test_exports(self):
        self.assertEqual(
            sorted(runtime_interfaces.__all__),
            sorted(
                [
                    "GovernanceGate",
                    "PassiveLearner",
                    "get_governance_gate",
                    "get_passive_learner",
                ]
            ),
        )

    def test_governance_protocol_runtime_checkable(self):
        class FakeGate:
            def should_auto_approve(self, proposal):
                return False

            def submit(self, proposal):
                return "p1"

            def approve(self, proposal_id, reviewer="system", notes=None):
                return True

            def reject(self, proposal_id, reviewer="system", reason=None):
                return False

            def start_canary(self, proposal_id, scope="test"):
                return True

            def complete_canary(self, proposal_id, success, metrics=None):
                return success

            def publish(self, proposal_id):
                return True

            def rollback(self, proposal_id, reason):
                return True

            def get_pending(self):
                return []

            def get_approved(self):
                return []

            def get_published(self):
                return []

            def get_stats(self):
                return {}

        self.assertIsInstance(FakeGate(), governance_iface.GovernanceGate)

    def test_passive_learning_protocol_runtime_checkable(self):
        class FakeLearner:
            def analyze(self, days=7):
                return {}

            def identify_improvements(self, days=7):
                return []

            def generate_proposals(self):
                return 0

            def run_cycle(self):
                return {}

            def analyze_rule_effectiveness(self):
                return []

        self.assertIsInstance(FakeLearner(), passive_iface.PassiveLearner)

    def test_governance_factory_delegates_to_components_module(self):
        sentinel = object()
        components_pkg = types.ModuleType("components")
        governance_mod = types.ModuleType("components.governance")
        governance_mod.get_governance_gate = lambda: sentinel
        components_pkg.governance = governance_mod

        with unittest.mock.patch.dict(
            sys.modules,
            {"components": components_pkg, "components.governance": governance_mod},
            clear=False,
        ):
            self.assertIs(governance_iface.get_governance_gate(), sentinel)

    def test_passive_learning_factory_delegates_to_components_module(self):
        sentinel = object()
        components_pkg = types.ModuleType("components")
        passive_mod = types.ModuleType("components.passive_learning")
        passive_mod.get_passive_learner = lambda: sentinel
        components_pkg.passive_learning = passive_mod

        with unittest.mock.patch.dict(
            sys.modules,
            {"components": components_pkg, "components.passive_learning": passive_mod},
            clear=False,
        ):
            self.assertIs(passive_iface.get_passive_learner(), sentinel)


if __name__ == "__main__":
    unittest.main()
