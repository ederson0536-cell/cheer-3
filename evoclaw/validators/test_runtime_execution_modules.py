#!/usr/bin/env python3
"""Regression tests for runtime execution modules."""

import unittest

from evoclaw.runtime.components.real_executor import RealExecutor
from evoclaw.runtime.components.skill_executor import SkillExecutor
from evoclaw.runtime.complete_runtime import CompleteEvoClawRuntime
from evoclaw.runtime.integrated_processor import process_message


class RuntimeExecutionModulesTests(unittest.TestCase):
    def test_real_executor_unknown_skill_has_error_code(self):
        executor = RealExecutor()
        result = executor.execute("missing_skill", {"goal": "x"})
        self.assertFalse(result.get("success"))
        self.assertEqual(result.get("error_code"), "unknown_skill")

    def test_skill_executor_is_not_placeholder_for_weather(self):
        executor = SkillExecutor()
        result = executor.execute("weather_skill", {"goal": "今天天气"})
        payload = str(result)
        self.assertNotIn("simulated", payload)
        self.assertNotIn("Would", payload)

    def test_complete_runtime_status_contains_startup_checks(self):
        runtime = CompleteEvoClawRuntime()
        status = runtime.get_status()
        self.assertIn("startup_checks", status)
        self.assertIsInstance(status["startup_checks"], dict)

    def test_integrated_processor_rejects_empty_message(self):
        with self.assertRaises(ValueError):
            process_message("   ")


if __name__ == "__main__":
    unittest.main()
