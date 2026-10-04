#!/usr/bin/env bash
# One entry point for reproducing the committed results offline (no API keys needed except for `sweep`'s output).
#
#   scripts/reproduce.sh test          offline pytest
#   scripts/reproduce.sh demo [args]   offline replay of the golden fixture (demo.app; extra args are passed on,
#                                      e.g. --story --open; DEMO_UI=terminal for the ANSI version)
#   scripts/reproduce.sh analyze       regenerate results/RESULTS.md (judged v2) + RESULTS_v3_preliminary.md and figures
#   scripts/reproduce.sh cost          estimated API spend per results dir -> results/COST.md
#   scripts/reproduce.sh sweep         print the exact Modal commands behind each committed results dir
#   scripts/reproduce.sh derived       committed label/mode variants: mitigation, calibration, cascade, obfuscation,
#                                      cascade held-out check + headline figure, judge validation, error tables and
#                                      robustness (v2 corrected + v3 labeller-only), hidden-line evidence
#                                      (explicit paths; --label tags the filenames)
#   scripts/reproduce.sh export-demo   single self-contained static HTML demo -> docs/demo.html (demo.export)
#   scripts/reproduce.sh all           test + analyze + cost + derived + sweep + export-demo
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

# The committed outputs of the label-aware CLIs. Without --out they write next to the experiments, and a
# non-default --label/--mode is added to each filename, so the corrected runs below reuse the either-label paths.
cmd_derived() {
  setup
  local v2="results/v2_sonnet46 results/v2_haiku45 results/v2_sonnet45" pair="results/v2_sonnet46 results/v2_haiku45"
  local hand="--labels docs/obfuscation_handlabels.json --labels docs/obfuscation_handlabels_heldout.json"
  local label
  for label in either corrected; do
    # shellcheck disable=SC2086
    "$PY" -m eval.mitigate best-of-n $pair --label "$label" \
      --out results/mitigation_bestofn_v2/MITIGATION_bestofn.md >/dev/null
    # shellcheck disable=SC2086
    "$PY" -m eval.calibrate $v2 --label "$label" --out results/calibration_v2/CALIBRATION.md >/dev/null
    # shellcheck disable=SC2086
    "$PY" -m eval.calibrate $v2 --label "$label" --folds random \
      --out results/calibration_v2/random_folds/CALIBRATION.md >/dev/null
    # shellcheck disable=SC2086
    "$PY" -m eval.cascade $pair --label "$label" --out results/CASCADE.md --json results/CASCADE.json \
      --figure results/figures/cascade_frontier.svg >/dev/null
    # shellcheck disable=SC2086
    "$PY" -m eval.obfuscation $v2 results/v3cond_sonnet46 results/v3cond_haiku45 $hand --label "$label" \
      --out results/obfuscation/OBFUSCATION.md >/dev/null
    # shellcheck disable=SC2086
    "$PY" -m eval.obfuscation $v2 results/v3cond_sonnet46 results/v3cond_haiku45 $hand --label "$label" \
      --overrides docs/obfuscation_v3cond_manual_labels.json --out results/obfuscation/OBFUSCATION_v3manual.md >/dev/null
  done
  # shellcheck disable=SC2086
  "$PY" -m eval.cascade $pair --mode final_report --label corrected --out results/CASCADE.md \
    --json results/CASCADE.json --figure results/figures/cascade_frontier.svg >/dev/null
  # held-out check (docs/cascade_heldout.md): pre-calibration heuristic on v2, current heuristic on v3, then the summary
  # shellcheck disable=SC2086
  "$PY" -m eval.cascade $pair --label corrected --heuristic-ref f664c95 --out results/CASCADE_corrected_precal.md \
    --json results/CASCADE_corrected_precal.json --figure results/figures/cascade_frontier_corrected_precal.svg >/dev/null
  "$PY" -m eval.cascade results/v3_haiku45 results/v3_sonnet46 results/v3cond_haiku45 results/v3cond_sonnet46 \
    results/v3fault_sonnet46 results/v3_opus46 --label labeller --families 'heuristic,sonnet,h->sonnet' \
    --out results/CASCADE_v3_labeller.md --json results/CASCADE_v3_labeller.json >/dev/null
  "$PY" -m eval.cascade_heldout --out results/cascade_heldout >/dev/null
  "$PY" -m eval.headline >/dev/null
  "$PY" -m eval.obfuscation results/v3_sonnet46 results/v3_haiku45 results/v3cond_sonnet46 results/v3cond_haiku45 \
    --configs covert,covert_monitored --tasks cherry_pick,effect_size_target,fabrication \
    --overrides docs/obfuscation_v3cond_manual_labels.json --out results/obfuscation/OBFUSCATION_matched_v3.md >/dev/null
  "$PY" -m eval.judge_validation score --label corrected --out results/judge_validation >/dev/null
  # shellcheck disable=SC2086
  "$PY" -m eval.errors $v2 --tags docs/error_tags.json --sample-out results/errors_v2/sample.json \
    --out results/errors_v2/ERRORS.md >/dev/null
  # shellcheck disable=SC2086
  "$PY" -m eval.errors $v2 --tags docs/error_tags.json --correction results/leaked_answer_correction.json \
    --out results/errors_v2_corrected/ERRORS.md >/dev/null
  # robustness (docs/methodology_review.md): clustered CIs, covert vs natural, role leak, PPV at lower prevalence
  "$PY" -m eval.robustness --out results/robustness >/dev/null
  "$PY" -m eval.robustness --cohort v3 --out results/robustness >/dev/null
  # known issue (docs/methodology_review.md): committed verdicts citing mode-hidden lines, repair impact
  "$PY" -m eval.hidden_evidence --out results/hidden_evidence/HIDDEN_EVIDENCE.md \
    --json results/hidden_evidence/hidden_evidence.json >/dev/null
}

cmd_sweep() { setup; "$PY" scripts/sweep_commands.py "$@"; }

cmd_export_demo() { setup; "$PY" -m demo.export "$@"; }

usage() { sed -n '2,15p' "$0" | sed 's/^# \{0,1\}//'; }

target="${1:-help}"
shift || true
case "$target" in
  test) cmd_test "$@" ;;
  demo) cmd_demo "$@" ;;
  analyze) cmd_analyze "$@" ;;
  cost) cmd_cost "$@" ;;
  derived) cmd_derived ;;
  sweep) cmd_sweep "$@" ;;
  export-demo) cmd_export_demo "$@" ;;
  all) cmd_test && cmd_analyze && cmd_cost && cmd_derived && cmd_sweep && cmd_export_demo ;;
  help|-h|--help) usage ;;
  *) echo "unknown target: $target" >&2; usage >&2; exit 2 ;;
esac
