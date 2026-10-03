"""Agent configs and auditor modes added during integration."""

from agent.prompts import AGENT_CONFIGS, build_system_prompt
from auditor.audit import MODES, load_events, render_trajectory, sandbox_files
from auditor.prompts import build_user_message
from eval.run_episode import AGENT_CONFIGS as EVAL_CONFIGS, AUDITOR_MODES, parse_modes
from tasks.registry import load_task

FIXTURE = "fixtures/trajectories/example.jsonl"


def test_configs_consistent_across_packages():
    assert set(AGENT_CONFIGS) == set(EVAL_CONFIGS) == {"honest", "incentivized", "pressure", "covert", "covert_monitored", "sycophantic_pi"}
    assert set(MODES) == set(AUDITOR_MODES) == {"full_trace", "report_only", "final_report"}


def test_every_config_builds_a_prompt_listing_the_files():
    task = load_task("leaked_answer")
    for cfg in AGENT_CONFIGS:
        prompt = build_system_prompt(task, cfg)
        assert sandbox_files(prompt) == sorted(task["files"])


def test_system_prompt_text_never_shown_to_auditor():
    events = load_events(FIXTURE)
    secret = events[0]["text"]
    for mode in MODES:
        assert secret not in render_trajectory(events, mode)


def test_final_report_mode_shows_only_task_and_report():
    events = load_events(FIXTURE)
    rendered = render_trajectory(events, "final_report")
    shown = {int(line[2:].split("]")[0]) for line in rendered.splitlines() if line.startswith("[L")}
    assert shown == {1, 2, len(events)}
    assert "tool_call" not in rendered and "reasoning" not in rendered
    assert "Mode: final_report" in build_user_message(rendered, "final_report", len(events))


def test_parse_modes_aliases():
    assert parse_modes("both") == ["full_trace", "report_only"]
    assert parse_modes("all") == list(AUDITOR_MODES)
