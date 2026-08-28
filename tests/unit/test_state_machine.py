# DevAgent
# Autor: Dayvid Santana
# Data: 28/08/2026
# Objetivo: Cobrir transições, checkpoints e proteção contra loops da máquina de estados.
from __future__ import annotations

import pytest

from dev_agent.core.models import SubAgentResult, TaskStatus
from dev_agent.core.state_machine import TaskStateMachine
from dev_agent.errors import InvalidStateTransitionError, TaskLoopDetectedError


def test_happy_path_transitions_reach_completed():
    machine = TaskStateMachine("job-1")
    for target in (TaskStatus.DISCOVERING, TaskStatus.PLANNING, TaskStatus.EXECUTING, TaskStatus.TESTING, TaskStatus.REVIEWING, TaskStatus.COMPLETED):
        machine.transition(target)
    assert machine.status == TaskStatus.COMPLETED
    assert machine.is_terminal


def test_invalid_transition_is_rejected():
    machine = TaskStateMachine("job-1")
    with pytest.raises(InvalidStateTransitionError, match="received.*testing"):
        machine.transition(TaskStatus.TESTING)


def test_terminal_states_have_no_outgoing_transitions_except_rollback():
    machine = TaskStateMachine("job-1")
    machine.transition(TaskStatus.DISCOVERING)
    machine.transition(TaskStatus.PLANNING)
    machine.transition(TaskStatus.EXECUTING)
    machine.transition(TaskStatus.TESTING)
    machine.transition(TaskStatus.REVIEWING)
    machine.transition(TaskStatus.COMPLETED)
    with pytest.raises(InvalidStateTransitionError):
        machine.transition(TaskStatus.EXECUTING)


def test_max_steps_guard_stops_runaway_pipelines():
    machine = TaskStateMachine("job-1", max_steps=2)
    machine.transition(TaskStatus.DISCOVERING)
    machine.transition(TaskStatus.PLANNING)
    with pytest.raises(TaskLoopDetectedError, match="máximo de 2 passos"):
        machine.transition(TaskStatus.EXECUTING)


def test_phase_repeat_guard_detects_a_stuck_retry_cycle():
    machine = TaskStateMachine("job-1", max_phase_repeats=2, max_steps=100)
    machine.transition(TaskStatus.DISCOVERING)
    machine.transition(TaskStatus.PLANNING)
    machine.transition(TaskStatus.EXECUTING)
    machine.transition(TaskStatus.TESTING)
    machine.transition(TaskStatus.EXECUTING)
    machine.transition(TaskStatus.TESTING)
    with pytest.raises(TaskLoopDetectedError, match="repetida"):
        machine.transition(TaskStatus.EXECUTING)


def test_checkpoint_captures_phase_results_and_changed_files():
    machine = TaskStateMachine("job-1")
    machine.transition(TaskStatus.DISCOVERING)
    machine.transition(TaskStatus.PLANNING)
    results = [SubAgentResult(agent="context", summary="ok")]
    point = machine.checkpoint(step_index=1, completed_agents=["context"], results=results, changed_files=["a.py"])
    assert point.job_id == "job-1"
    assert point.phase == TaskStatus.PLANNING
    assert machine.latest_checkpoint is point

    results.append(SubAgentResult(agent="requirements", summary="ok"))
    assert len(point.results) == 1, "o checkpoint não deve refletir mutações posteriores da lista original"
