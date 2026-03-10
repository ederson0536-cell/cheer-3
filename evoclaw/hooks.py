#!/usr/bin/env python3
"""Unified hook entrypoints for EvoClaw."""

from evoclaw.feedback_system import (
    after_subtask as _after_subtask,
    after_task as _after_task,
    before_subtask as _before_subtask,
    before_task as _before_task,
    governance_gate as _governance_gate,
    handle_user_confirmation_reply as _handle_user_confirmation_reply,
)


def before_task(task):
    """Single public before_task entry."""
    return _before_task(task)


def before_subtask(subtask):
    return _before_subtask(subtask)


def after_subtask(subtask, result):
    return _after_subtask(subtask, result)


def after_task(task, result):
    return _after_task(task, result)


def governance_gate():
    return _governance_gate()


def handle_user_confirmation_reply(message: str):
    return _handle_user_confirmation_reply(message)
