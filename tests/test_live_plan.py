"""Live launch planning, flag validation and resumption: never execute a live job."""

import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts import live_plan as lp


@pytest.fixture(scope="module")
def rates():
    return lp.cost_rates()


@pytest.fixture(scope="module")
def flags():
    # Modal's --help parses local entrypoint flags without authentication or deployment.
    return lp.help_flags()


@pytest.fixture(scope="module")
def steps(rates, flags):
    return [lp.build_step(key, lp.ROOT, rates, flags) for key in lp.ORDER]


def test_every_referenced_module_and_flag_parses_help(steps, flags):
    assert set(flags) == set(lp.MODULES)
    lp.validate_commands(steps, flags)
    for step in steps:
        assert not step.blocked or step.key == "rubric-v3", step.blocked
        for cmd in step.commands:
            used = {a for a in cmd.argv[3:] if a.startswith("--")}
            if step.key == "rubric-v3" and "--rubric" not in flags[cmd.argv[2]]:
                used -= {"--rubric"}
                assert any("PLACEHOLDER" in s for s in step.blocked)
            assert used <= flags[cmd.argv[2]], cmd.argv


def test_priorities_counts_and_existing_episodes_are_not_resampled(steps):
    assert tuple(s.key for s in steps) == lp.ORDER
    finish = next(s for s in steps if s.key == "finish-v3")
    missing = set()
    for name, _, configs, n, _ in lp.SWEEPS:
        source = lp.ROOT / "results" / name / "trajectories"
        missing |= {source / f"{tid}.jsonl" for tid in lp.grid(configs, n)
                    if not lp.complete(source / f"{tid}.jsonl")}
    planned = [p for cmd in finish.commands if cmd.argv[2] == "eval/sweep.py"
               for p in cmd.outputs if p.suffix == ".jsonl"]
    assert set(planned) == missing and len(planned) == len(missing)
    assert len(planned) == 370
    assert next(s for s in steps if s.key == "judge-v3").calls["judge", lp.OPUS] == 450
    assert next(s for s in steps if s.key == "judge-new-v3").calls["judge", lp.OPUS] == 370
    for cmd in finish.commands:
        if cmd.argv[2] == "eval/sweep.py" and "v3fault_sonnet46" in str(cmd.outputs[0]):
            assert cmd.argv[cmd.argv.index("--fault-rate") + 1] == "0.5"


def test_models_modes_subset_and_separate_output_directories(steps):
    for key, n in (("hard-cases", 32), ("monitor-attacks", 70)):
        step = next(s for s in steps if s.key == key)
        assert len(step.commands) == 2 and sum(step.calls.values()) == n * 3 * 2
        for cmd in step.commands:
            assert cmd.argv[cmd.argv.index("--modes") + 1] == "all"
            model = cmd.argv[cmd.argv.index("--auditor-model") + 1]
            assert model in str(cmd.outputs[0])
    agentic = next(s for s in steps if s.key == "agentic")
    assert sum(agentic.calls.values()) == 12 * 2 * 8
    for cmd in agentic.commands:
        assert cmd.argv[cmd.argv.index("--auditor") + 1] == "agentic"
        ids = cmd.argv[cmd.argv.index("--only") + 1].split(",")
        assert len(ids) == 12 and all(i.endswith("ep000") for i in ids)
    rejudge = next(s for s in steps if s.key == "rejudge-leaked")
    assert sum(rejudge.calls.values()) == 60
    assert all("rejudge_matched/judgments" in str(p) for cmd in rejudge.commands for p in cmd.outputs)


def test_costs_use_repriced_token_rows_and_actual_agent_turns(rates, steps):
    from eval.cost import usd

    totals = [0.0, 0]
    for line in (lp.ROOT / "results/COST.md").read_text().splitlines():
        cells = [v.strip().strip("`") for v in line.strip("|").split("|")]
        if len(cells) == 10 and cells[0].startswith("results/") and cells[1] == "judge":
            tokens = {k: int(v.replace(",", "")) for k, v in zip(lp.TOKEN_KEYS, cells[4:8])}
            totals[0] += usd(tokens, cells[2])
            totals[1] += int(cells[3])
    assert rates["judge", lp.OPUS].usd_per_call == pytest.approx(totals[0] / totals[1])
    assert rates["agent", lp.SONNET].calls_per_episode > 1
    assert all(s.estimate(rates) > 0 for s in steps)


def test_dry_run_default_equals_explicit_and_does_not_change_results():
    env = {k: v for k, v in os.environ.items() if not k.startswith(("ANTHROPIC_", "MODAL_"))}
    before = subprocess.check_output(["git", "status", "--porcelain"], cwd=lp.ROOT)
    results_before = {p: p.stat().st_mtime_ns for p in (lp.ROOT / "results").rglob("*") if p.is_file()}
    outputs = []
    for args in ([], ["--dry-run"]):
        result = subprocess.run([sys.executable, "scripts/live_plan.py", *args], cwd=lp.ROOT,
                                env=env, capture_output=True, text=True, timeout=30)
        assert result.returncode == 0, result.stderr
        assert "no Anthropic calls" in result.stdout
        assert "PLACEHOLDER" in result.stdout or "--rubric" in result.stdout
        outputs.append(result.stdout)
    assert outputs[0] == outputs[1]
    assert subprocess.check_output(["git", "status", "--porcelain"], cwd=lp.ROOT) == before
    assert {p: p.stat().st_mtime_ns for p in (lp.ROOT / "results").rglob("*") if p.is_file()} == results_before


def test_benchmark_resumes_and_missing_corpus_is_blocked(tmp_path, rates, flags):
    cases = tmp_path / "fixtures/hard_cases"
    cases.mkdir(parents=True)
    (cases / "case.jsonl").write_text("{}")
    (cases / "case.label.json").write_text("{}")
    first = lp.build_step("hard-cases", tmp_path, rates, flags)
    assert sum(first.calls.values()) == 6
    output = first.commands[0].outputs[0]
    output.parent.mkdir(parents=True)
    output.write_text('{"hack_detected": false, "confidence": 0.1}')
    second = lp.build_step("hard-cases", tmp_path, rates, flags)
    assert sum(second.calls.values()) == 5
    assert output not in [p for c in second.commands for p in c.outputs]
    missing = lp.build_step("monitor-attacks", tmp_path, rates, flags)
    assert missing.blocked and "--build" in " ".join(missing.notes)


def test_invalid_flags_and_module_are_blocked(tmp_path):
    step = lp.Step("test", "test")
    step.add("missing.py", ["--invalid"], [])
    lp.validate_commands([step], {}, tmp_path)
    assert len(step.blocked) == 2


def test_execute_rechecks_outputs_and_can_resume(tmp_path, monkeypatch):
    output = tmp_path / "output.json"
    calls = []

    def build(key, *args):
        step = lp.Step(key, key)
        if not lp.complete(output):
            step.add("job.py", [], [output])
        return step

    def runner(argv, **kwargs):
        calls.append(argv)
        output.write_text('{"done": true}')
        return SimpleNamespace(returncode=0)

    (tmp_path / "job.py").write_text("")
    monkeypatch.setattr(lp, "build_step", build)
    assert lp.execute(["test"], tmp_path, {}, {"job.py": set()}, runner) == 0
    assert lp.execute(["test"], tmp_path, {}, {"job.py": set()}, runner) == 0
    assert len(calls) == 1
    output.unlink()
    assert lp.execute(["test"], tmp_path, {}, {"job.py": set()},
                      lambda *a, **k: SimpleNamespace(returncode=0)) == 1
    assert lp.execute(["test"], tmp_path, {}, {"job.py": set()},
                      lambda *a, **k: SimpleNamespace(returncode=7)) == 7


def test_blocked_rubric_does_not_prevent_later_rejudge(tmp_path, monkeypatch):
    seen = []

    def build(key, *args):
        seen.append(key)
        return lp.Step(key, key, blocked=["PLACEHOLDER"] if key == "rubric-v3" else [])

    monkeypatch.setattr(lp, "build_step", build)
    assert lp.execute(["rubric-v3", "rejudge-leaked"], tmp_path, {}, {}) == 2
    assert seen == ["rubric-v3", "rejudge-leaked"]


def test_budget_gate_prevents_execution(monkeypatch, rates, flags):
    monkeypatch.setattr(lp, "cost_rates", lambda: rates)
    monkeypatch.setattr(lp, "help_flags", lambda: flags)
    monkeypatch.setattr(lp, "execute", lambda *a: pytest.fail("live execution is forbidden"))
    assert lp.main(["--run", "--steps", "hard-cases", "--max-usd", "0"]) == 2


def test_run_prerequisites_do_not_expose_auth(monkeypatch):
    from modal.config import config

    monkeypatch.setattr(config, "get", lambda key: None)
    assert lp.run_prerequisites([]) == ["Modal credentials not configured; authenticate Modal before --run."]


@pytest.mark.parametrize("module", [*lp.MODULES, "scripts/live_plan.py"])
def test_python_module_help(module):
    args = [sys.executable, module] if module.startswith("scripts/") else [sys.executable, "-m", module[:-3].replace("/", ".")]
    result = subprocess.run([*args, "--help"], cwd=lp.ROOT, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0 and "usage" in result.stdout.lower(), result.stderr
