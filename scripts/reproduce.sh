#!/usr/bin/env bash
# One entry point for reproducing the committed results offline (no API keys needed except for `sweep`'s output).
#
#   scripts/reproduce.sh test          offline pytest
#   scripts/reproduce.sh demo [args]   offline replay of the golden fixture (demo.app; extra args are passed on,
#                                      e.g. --story --open; DEMO_UI=terminal for the ANSI version)
#   scripts/reproduce.sh analyze       regenerate results/RESULTS.md (judged v2) + RESULTS_v3_preliminary.md and figures
#   scripts/reproduce.sh cost          estimated API spend per results dir -> results/COST.md
#   scripts/reproduce.sh sweep         print the exact Modal commands behind each committed results dir
#   scripts/reproduce.sh export-demo   single self-contained static HTML demo -> docs/demo.html (demo.export)
#   scripts/reproduce.sh all           test + analyze + cost + sweep + export-demo
set -euo pipefail

cd "$(dirname "$0")/.."
PY="${PYTHON:-.venv/bin/python}"
UV="${UV:-$(command -v uv || echo "$HOME/.local/bin/uv")}"

setup() {
  if [[ ! -x "$PY" ]]; then
    "$UV" venv --allow-existing -p 3.11 .venv
    "$UV" pip install -p .venv -e .
  fi
}

# Experiment dirs: every results/<exp>/ with trajectories (cost, sweep) / with audited episodes (analyze).
traj_dirs() { for d in results/*/; do [[ -d "$d/trajectories" ]] && echo "${d%/}"; done; }
episode_dirs() { for d in results/*/; do [[ -d "$d/episodes" ]] && echo "${d%/}"; done; }

cmd_test() { setup; "$PY" -m pytest -q "$@"; }

cmd_demo() {
  setup
  if [[ "${DEMO_UI:-web}" == terminal ]]; then
    "$PY" -m demo.terminal --flags-progressive --delay 0.8 "$@"
  else
    "$PY" -m demo.app --port "${PORT:-8000}" --delay 1.2 "$@"
  fi
}

cmd_analyze() {
  setup
  # shellcheck disable=SC2046
  # Headline: judged v2 sweeps only. v3* are labeller-only (no judge labels) and reported separately.
  "$PY" -m eval.analyze results/v2_sonnet46 results/v2_haiku45 results/v2_sonnet45 \
    --out results/RESULTS.md --figures --figures-dir results/figures "$@"
  # shellcheck disable=SC2046
  "$PY" -m eval.analyze $(episode_dirs | grep '/v3') \
    --out results/RESULTS_v3_preliminary.md --figures --figures-dir results/figures_v3 "$@"
}

cmd_cost() {
  setup
  # shellcheck disable=SC2046
  "$PY" -m eval.cost $(traj_dirs) --by-dir --out results/COST.md "$@"
}

cmd_sweep() { setup; "$PY" scripts/sweep_commands.py "$@"; }

cmd_export_demo() { setup; "$PY" -m demo.export "$@"; }

usage() { sed -n '2,11p' "$0" | sed 's/^# \{0,1\}//'; }

target="${1:-help}"
shift || true
case "$target" in
  test) cmd_test "$@" ;;
  demo) cmd_demo "$@" ;;
  analyze) cmd_analyze "$@" ;;
  cost) cmd_cost "$@" ;;
  sweep) cmd_sweep "$@" ;;
  export-demo) cmd_export_demo "$@" ;;
  all) cmd_test && cmd_analyze && cmd_cost && cmd_sweep && cmd_export_demo ;;
  help|-h|--help) usage ;;
  *) echo "unknown target: $target" >&2; usage >&2; exit 2 ;;
esac
