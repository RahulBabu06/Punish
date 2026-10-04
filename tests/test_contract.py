"""ARCHITECTURE.md's documented signatures, enums and fields match the code, so contract drift fails CI."""

import inspect
import json
import re
from pathlib import Path

import agent.prompts
import agent.runner
import agent.tools
import auditor.audit
import auditor.prompts
import eval.metrics
import eval.run_episode
import tasks.registry
import tasks.validate_labels

ROOT = Path(__file__).resolve().parent.parent
DOC = (ROOT / "ARCHITECTURE.md").read_text(encoding="utf-8")
TRAJECTORY = ROOT / "fixtures" / "trajectories" / "example.jsonl"
VERDICT = ROOT / "fixtures" / "verdicts" / "example.json"
DEFINITIONS = {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in (ROOT / "tasks" / "definitions").glob("*.json")}

INTERFACES = {
    "list_tasks": tasks.registry.list_tasks,
    "load_task": tasks.registry.load_task,
    "label": tasks.registry.label,
    "run_agent": agent.runner.run_agent,
    "audit": auditor.audit.audit,
    "run_episode": eval.run_episode.run_episode,
    "compute_metrics": eval.metrics.compute_metrics,
}


def section(start: str, end: str) -> str:
    return DOC.split(start, 1)[1].split(end, 1)[0]


def table_rows(text: str) -> list[list[str]]:
    return [[c.strip() for c in line.strip().strip("|").split("|")] for line in text.splitlines() if line.startswith("| `")]


def ticked(text: str) -> list[str]:
    return re.findall(r"`([^`]+)`", text)


def row(text: str, field: str) -> list[str]:
    return next(r for r in table_rows(text) if ticked(r[0]) == [field])


def after(marker: str) -> list[str]:
    """Backticked values in the ∈-list that follows ``marker`` (up to the next parenthesis or full stop)."""
    tail = DOC.split(marker, 1)[1]
    return ticked(re.split(r"\(|\.\s", tail, maxsplit=1)[0])


def _annotation(a) -> str:
    return a if isinstance(a, str) else inspect.formatannotation(a)


def code_signature(fn) -> str:
    sig, parts = inspect.signature(fn), []
    for p in sig.parameters.values():
        if p.kind is p.KEYWORD_ONLY and "*" not in parts:
            parts.append("*")
        text = p.name
        if p.annotation is not p.empty:
            text += f": {_annotation(p.annotation)}" + (f" = {p.default!r}" if p.default is not p.empty else "")
        elif p.default is not p.empty:
            text += f"={p.default!r}"
        parts.append(text)
    return f"({', '.join(parts)}) -> {_annotation(sig.return_annotation)}"


def documented_signatures() -> dict[str, str]:
    block = section("## Python interfaces", "## Component specs").split("```python", 1)[1].split("```", 1)[0]
    flat = re.sub(r"\s+", " ", re.sub(r"#[^\n]*", "", block)).replace("( ", "(")
    return {m[1]: f"({m[2]}) -> {m[3].strip()}" for m in re.finditer(r"def (\w+)\((.*?)\) -> ([^:]+): \.\.\.", flat)}


def test_interface_signatures_match_code():
    documented = documented_signatures()
    assert documented.keys() == INTERFACES.keys()
    for name, fn in INTERFACES.items():
        assert documented[name] == code_signature(fn), name


def test_agent_configs():
    identifiers = next(line for line in DOC.splitlines() if line.startswith("- `agent_config`"))
    documented = tuple(re.findall(r'"(\w+)"', identifiers))
    specs = tuple(re.findall(r"^  - `(\w+)` —", section("### `agent/`", "### `auditor/`"), re.M))
    assert documented == specs == agent.prompts.AGENT_CONFIGS == agent.runner.AGENT_CONFIGS
    assert documented == eval.run_episode.AGENT_CONFIGS
    assert set(agent.prompts.USER_PREFIXES) <= set(documented)


def test_auditor_modes_rubrics_and_backends():
    verdict = section("### 3. Verdict", "### 4. Episode result")
    modes = tuple(ticked(row(verdict, "auditor_mode")[2]))
    assert modes == auditor.audit.MODES == eval.run_episode.AUDITOR_MODES
    assert tuple(re.findall(r"^  - `(\w+)` —", section("### `auditor/`", "### `tasks/`"), re.M)) == modes
    assert tuple(after("`rubric` ∈")) == auditor.prompts.RUBRICS
    assert tuple(after("`thinking` ∈")) == agent.runner.THINKING_MODES
    episode = section("### 4. Episode result", "## Python interfaces")
    backends = tuple(ticked(row(episode, "auditor_backend")[2]))
    assert backends == eval.run_episode.AUDITOR_BACKENDS
    assert "`eval.run_episode` takes `claude` or `heuristic`" in re.sub(r"\s+", " ", DOC)


def test_hack_type_vocabulary():
    vocab = section("`hack_types` vocabulary (closed set", "### 4. Episode result")
    documented = tuple(ticked(r[0])[0] for r in table_rows(vocab))
    assert documented == auditor.audit.HACK_TYPES == tuple(auditor.prompts.HACK_TYPE_DEFINITIONS)
    for task in DEFINITIONS.values():
        assert set(task["exploit"]["expected_hack_types"]) <= set(documented), task["id"]


def test_exploit_types_and_task_list():
    task_section = section("### 1. Task definition", "### 2. Trajectory")
    cell = row(task_section, "exploit.type")[2]
    listed, _, aliases = cell.partition(";")
    assert set(ticked(listed)) == {t["exploit"]["type"] for t in DEFINITIONS.values()}
    documented_aliases = dict(re.findall(r"`(\w+)` is `(\w+)`", aliases))
    assert documented_aliases == {k: t["exploit"]["type"] for k, t in DEFINITIONS.items() if t["exploit"]["type"] != k}
    layout = set(re.findall(r"── (\w+)\.json", section("├── tasks/", "├── agent/")))
    assert layout == set(DEFINITIONS) == set(tasks.registry.list_tasks())


def test_tools_usage_and_verdict_fields():
    trajectory = section("### 2. Trajectory", "### 3. Verdict")
    assert tuple(ticked(row(trajectory, "tool_call")[2].split(".")[0])[1:]) == agent.tools.TOOL_NAMES
    tool_args = {r[0].strip("`"): tuple(re.findall(r'"(\w+)"', r[1])) for r in table_rows(trajectory) if r[0].strip("`") in agent.tools.TOOL_ARGS}
    assert tool_args == agent.tools.TOOL_ARGS
    usage = tuple(re.findall(r'"(\w+)"', row(trajectory, "message")[2].split("{", 1)[1].split("}", 1)[0]))
    assert usage == agent.runner.USAGE_KEYS == auditor.audit.USAGE_KEYS
    verdict = section("### 3. Verdict", "`hack_types` vocabulary (closed set")
    fields = [ticked(r[0])[0] for r in table_rows(verdict)]
    top = tuple(f for f in fields if "." not in f and f != "usage")
    assert top == auditor.audit.VERDICT_KEYS == eval.run_episode.VERDICT_KEYS
    assert agent.runner.SCHEMA_VERSION == 1 and "`schema_version` (int, `1`)" in trajectory


def test_episode_result_fields(tmp_path):
    episode_doc = section("### 4. Episode result", "## Python interfaces")
    rows = table_rows(episode_doc)
    required = {f for r in rows if r[1] != "optional" for f in ticked(r[0])}
    optional = {f for r in rows if r[1] == "optional" for f in ticked(r[0])}
    verdict = json.loads(VERDICT.read_text(encoding="utf-8"))
    episode = eval.run_episode.audit_existing(
        str(TRAJECTORY), results_dir=str(tmp_path), task={},
        audit_fn=lambda path, **kwargs: verdict, label_fn=lambda task, events: True)
    assert set(episode) == required
    assert optional == {"ground_truth_hack_types"} | {f"{f}_runtime" for f in tasks.validate_labels.RUNTIME_FIELDS}


def test_output_paths():
    flat = re.sub(r"\s+", " ", DOC)
    for mode, backend in (("full_trace", "claude"), ("report_only", "claude"), ("final_report", "heuristic")):
        suffix = eval.run_episode.output_suffix(mode, backend)
        assert (suffix == "") if (mode, backend) == ("full_trace", "claude") else f"`{suffix}`" in flat
    assert eval.run_episode.episode_path_for("x", "report_only", "claude", "R") == "R/episodes/x__report_only.json"
    assert "`episodes/<episode_id><suffix>.json`" in flat
