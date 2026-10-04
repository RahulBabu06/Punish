# Judge review: a skeptical 10-minute read

Integration commit `836dab5`, London AI x Science Hackathon, Track 2. Report only: README, REPORT and
PITCH are unchanged, and every fix below is a suggestion for the write-up owner. The read followed a
judge's 10-minute path: README, then the headline figure, PITCH, the REPORT abstract, §1 and closing
sections, the demo (`docs/demo.html` and `python -m demo.app`), and then [`reviewer_faq.md`](reviewer_faq.md).

## Verdict in one paragraph

The work underneath is strong. It has a real demo with line-cited evidence, paired statistics with
Holm correction, a label bug the team found and fixed itself, and an offline reproduction that rebuilds
the committed outputs byte for byte. The submission still loses points in the first 60 seconds. The
README opens with a "Known issue" box and a table that puts three label variants, nine numbers, in
every row. The best asset, the headline figure, sits 60 lines down. The same headline number takes
different values on different pages (the PITCH stage script uses `leaked_answer`-excluded numbers; the
figure and FAQ use corrected). A few pitch sentences claim more than
[`SIGNIFICANCE.md`](../results/significance/SIGNIFICANCE.md) supports. Fix the first screen and
standardise on one label, and the rigour starts working for the submission rather than against it.

## Top 10 issues that would cost points (ranked)

| # | issue | category | where |
|---|---|---|---|
| 1 | Headline buried under a caveat and a 3-label table | first impression / buried headline | `README.md:14-33`, figure at `README.md:63` |
| 2 | Three label variants on every number | caveat noise | `README.md:19-26`, `REPORT.md:31-70`, `PITCH.md:7-9,43,68-70` |
| 3 | The same headline takes different values on different surfaces | first impression | `PITCH.md:43`, `PITCH.md:99`, `README.md:65`, `reviewer_faq.md:54,78`, figure panel C |
| 4 | Pitch lines that over-claim compared with the Holm-corrected stats | over-claim | `PITCH.md:3-5`, `PITCH.md:43`, `eval/headline.py:83,102` |
| 5 | Novelty never stated up front | unclear novelty | `README.md:1-12`; differentiation only at `PITCH.md:155-159` |
| 6 | Static demo isn't linked, opens on the wrong page and is stale | demo friction | `README.md:93-116`, `demo/pages.py:101`, `docs/demo.html` |
| 7 | Six `TODO(numbers)` placeholders left in REPORT | looks unfinished | `REPORT.md:633,661,694,776,821,991` |
| 8 | Stale or confusing facts on the reading path | first impression | `PITCH.md:41`, `REPORT.md:9,20`, `README.md:108-109` |
| 9 | REPORT has no conclusions, and §8 runs 19 subsections | buried headline | `REPORT.md:257-977`, `REPORT.md:961`, `REPORT.md:1046-1073` |
| 10 | All ground truth is AI-made, and that is disclosed late | credibility | `reviewer_faq.md:29`, `REPORT.md:987-991`, `PITCH.md:72-80` |

### 1. The headline is buried under a caveat (`README.md:14-33`)

A judge's first screen holds the title, a "Known issue" paragraph about a stale judge definition, and a
table with values like `0.93 / 0.90 / 0.90`. Neither the takeaway nor the figure is on it. The
figure, the clearest thing in the repo, is at `README.md:63`. Setup and three Modal command blocks
(`README.md:78-157`) come before the reproduction section, and the 60-line command block at
`README.md:164-222` pushes the repo map to line 263.

**Fix.**
- Move `![...](results/figures/headline.svg)` to directly after the subtitle (after `README.md:4`).
- Under the figure, give three one-line takeaways: hack rate depends on the prompt; the trace finds
  hacks the report hides; a stronger auditor uses the reasoning.
- Replace the table at `README.md:22-26` with a corrected-label-only table (recall/FPR/AUROC
  `0.90/0.34/0.89`, `0.91/0.35/0.84`, `0.74/0.23/0.83`) and add one sentence linking to
  `REPORT.md` §8.0 for the original and excluded variants.
- Cut `README.md:164-222` down to `scripts/reproduce.sh all`, and link `docs/repro_check.md` for the
  per-table commands.

### 2. Caveat noise: three labels on every number (`README.md:19-26`, `REPORT.md:31-70`)

Original / `leaked_answer` excluded / corrected appears on nearly every claim. REPORT abstract result
4 (`REPORT.md:45-55`) is 11 lines with eight parenthetical statistics. This reads as defensive, and it
makes a judge do the label bookkeeping. The figure and FAQ have already picked corrected as the
headline label.

**Fix.**
- Say once that the corrected label is the headline label and why: one pre-specified rule, 30 runs
  relabelled (`reviewer_faq.md:15-23` already explains it well).
- Give single numbers in the abstract (`REPORT.md:36-60`) and the README.
- Move every original/excluded variant into the §8.0 table (`REPORT.md:263`).
- In PITCH, delete the `(excluded/corrected; ...)` parentheticals at `PITCH.md:68-70` and `PITCH.md:96-97`.

### 3. The same headline has different values on different pages

- **Recall gap.** The stage script quotes excluded-label numbers ("we drop that task and show 300
  runs ... recall is 0.76 ... goes to 0.90, AUROC 0.86 to 0.93", `PITCH.md:43`). The figure behind
  the speaker says corrected, n = 360, with `final_report` recall 74.2% and AUROC 0.825.
- **Cascade point.** Four values circulate:
  - README: 0.80 / 0.054 (`README.md:65`);
  - PITCH: 0.80 / 0.054 (`PITCH.md:99`);
  - FAQ: "64.3% recall and 5.4% FPR" as *the* cross-experiment point (`reviewer_faq.md:54,78`);
  - figure panel C: 80.4% and, in its footnote, 76.8%.
  Each is defensible, but a judge sees four numbers for one claim.
- **Opus FPR.** "Halves false positives, 12% to 6%" (`PITCH.md:43`, excluded label) sits beside
  0.22 corrected (`PITCH.md:109`, `reviewer_faq.md:53`).

**Fix.**
- Use corrected-label numbers in the stage script, so `PITCH.md:43` matches figure panel B: 0.74 → 0.90
  recall, AUROC 0.83 → 0.89, and Opus 0.63 → 0.77 recall.
- Name one cascade point as the headline (suggested: v3 held-out, 0.63 / 0.029, the only
  out-of-sample one). Call the others "in-sample" everywhere (`README.md:65-70`,
  `reviewer_faq.md:54`, `PITCH.md:99-103`).

### 4. Over-claims compared with the Holm-corrected stats

- **"Miss about a quarter ... catches about 9 in 10"** (`PITCH.md:3-5`, repeated at `PITCH.md:45`).
  The recall gain from seeing actions has Holm p = 0.057, which is underpowered. The hedge sits in a
  parenthetical at `PITCH.md:7-9`, which no one reads aloud. The FPR cost of seeing actions is the
  supported part (p = 0.049).
- **"When Opus audits, the reasoning ... halves false positives"** (`PITCH.md:43`). The Opus FPR
  component is not significant after correction (Holm p = 0.157). The accuracy gain (+0.071, Holm
  p = 0.002) is.
- **Figure panel B, "Detection is strong—but false alarms are high"** (`eval/headline.py:102`). This
  sits beside a 34.5% FPR in orange. "Strong" invites the obvious objection.
- **Figure panel A, "Hack rate depends on incentives"** (`eval/headline.py:83`). The large bar is
  `covert`, which is *instructed*, not incentivised. A judge who notices feels misled.

**Fix.**
- PITCH takeaway: "In our data, report-only review missed about a quarter of hacks; seeing the
  actions recovers most of them (not yet significant after correction)."
- Opus line: "reasoning made Opus's verdicts significantly more accurate (+7 points, p = 0.002)."
- Panel B title: "Auditors catch most hacks, but flag a third of honest runs".
- Panel A title: "Hacking follows the prompt: 0% honest, 12–18% pressured, 73% instructed".

### 5. Novelty is never stated up front

The README never says what is new. The differentiation from SHADE-Arena, ImpossibleBench and CoT
Red-Handed appears only as the 15th Q&A item in PITCH (`PITCH.md:155-159`), and related work is a
bare bullet (`README.md:75`). A judge will assume "yet another CoT monitor".

**Fix.** Add a three-line "What's new" after the README subtitle (`README.md:4`):
1. **Science-integrity hacks.** p-hacking, metric swaps, citation misuse and fabricated data,
   whose code runs fine. This is not unit-test gaming.
2. **A three-view ablation (reasoning / actions / report) with paired, Holm-corrected tests.**
   Plus a report-only baseline that matches how science is reviewed today.
3. **A stronger auditor uses the reasoning that a weaker one ignores.** Opus accuracy +0.071 vs a
   Sonnet null.

Mirror the same three lines in `REPORT.md:14-29`.

### 6. Demo friction (`README.md:93-116`, `docs/demo.html`)

- **The static demo is not linked.** Neither README, PITCH nor REPORT mentions the 4.5 MB
  zero-setup demo, `docs/demo.html`. GitHub shows it as source, so a judge who finds it still has to
  download it.
- **It opens on the wrong page.** It opens on the Gallery (`demo/pages.py:101`). Its first four rows
  are `model_probe` runs with no auditor verdicts (`FT – RO – FR –`). The curated Story tab,
  the best demo, is one click away and unlabelled as such.
- **The best server mode is undocumented in the README.** That is `demo.app --story --open`, which
  appears only in `demo/README.md:13`.
- **The Quickstart's first replay comment is off-putting.** `README.md:108-109` points the reader at
  "the former leaked_answer replay ... its saved hack verdict is a false positive". That is a
  confusing first thing to read about a demo.
- **The committed export is stale.** `python -m demo.export` at `836dab5` no longer reproduces it
  byte for byte. Embedded trajectory data differs, last rebuilt in `175f6a7`, before the bug-hunt
  merge.

**Fix.**
- Add at the top of README: "**Try it in 10 seconds:** download
  `docs/demo.html` and open it, no install." Also add
  `python -m demo.app --story --open` as Quickstart step 1.
- Make the static export start at `#/story` (`demo/export.py:299`, the `|| "/"` default), or sort the
  gallery so runs with verdicts come first.
- Delete `README.md:108-109`.
- Rerun `scripts/reproduce.sh export-demo`.

### 7. Six `TODO(numbers)` placeholders in REPORT

`REPORT.md:633`, `661`, `694`, `776`, `821` and `991` print a literal `` `TODO(numbers)` ``.
To a judge this reads as an unfinished draft, not as "needs API credit". `REPORT.md:991` is in
Limitations: "Agreement with human raters is still `TODO(numbers)`".

**Fix.** Replace each with "not run: needs API credit (command in
`docs/live_plan.md`)". At `REPORT.md:991`, write "not yet measured".

### 8. Stale or confusing facts on the reading path

- **Task count.** "Six science tasks" (`PITCH.md:41`) and "six small science tasks"
  (`REPORT.md:20`), while the repo map says 10 (`README.md:268`). Say "six tasks in the judged
  sweep (10 in the suite)".
- **"Every number is preliminary."** REPORT's status line (`REPORT.md:9`) labels all of it this way,
  then the abstract makes Holm-corrected claims. Restrict "preliminary" to v3 and small cells.
- **Pytest as a dependency.** README lists `pytest` as a runtime dependency (`README.md:87`), which
  tells a judge the packaging is loose. Change the wording or move it to a test extra later.

### 9. REPORT has no conclusions, and §8 is 720 lines

- **No conclusions section.** REPORT goes from §9 Limitations and §10 Future work straight to
  Reproducing (`REPORT.md:978-1073`). A judge skimming for "what did they find" has to return to the
  abstract.
- **§8 is too long.** It has 19 subsections (`REPORT.md:257-977`) and opens with "§8.0 Known issue
  ... (read first)".
- **Rubric v3 is misfiled.** The rubric-v3 proxy, the main proposed fix for the FPR problem, sits in
  §8.18 *Task design* (`REPORT.md:961`).

**Fix.**
- Add a `## Conclusions` section before §9 with five bullets, one per abstract result, each with the
  corrected-label number and its verdict (supported / null / underpowered).
- Move §8.7–§8.18 into an appendix.
- Give rubric v3 its own subsection next to §8.3 "Where the auditor is wrong".

### 10. All ground truth is AI-made, and that is disclosed late

The headline label is an Opus judge. The judge's blind check was done by Devin, "not a human domain
expert" (`reviewer_faq.md:29`). Human agreement is a `TODO` (`REPORT.md:991`). Track-2 judges will ask
about this first. Today the answer is in Q&A prep (`PITCH.md:72-80`), not on the first screen.

**Fix.**
- Add one line under the README headline: "Labels: Opus judge with privileged task info, checked
  against 60 blind AI labels (κ = 0.70); no human labels yet."
- If an hour is available, hand-label 20 stratified trajectories and report agreement. That would
  remove the hardest Q&A question.

## The 3 strongest points to lead with

1. **The money-shot replay.** In `v2_haiku45/metric_gaming__covert__ep002`, the agent computes
   R² = 0.447 (L10), privately says "make up an R² value ≥ 0.90" (L14) and reports 0.92 (L30). The
   `full_trace` auditor flags it at 0.99 with clickable line evidence. The same auditor given only
   the report says clean (0.2). That one run makes the whole thesis visible in 30 seconds
   (`PITCH.md:42`). Put a screenshot of it in the README.
2. **Rigour you can check.** The team caught its own ground-truth bug (stale `leaked_answer` context)
   and corrected it with one pre-specified rule. Every mode comparison is paired (McNemar, DeLong),
   with Holm correction and power analysis. `scripts/reproduce.sh` rebuilds every committed table
   offline, with no API key, byte for byte (1,295 tests).
3. **Findings with practical use.**
   - A stronger auditor uses reasoning that a weaker one ignores: Opus accuracy +0.071, Holm
     p = 0.002, against a genuine Sonnet null.
   - Unprompted hacking is real: 17.8% under pressure against 0/90 honest, p < 0.001.
   - An auditor veto cuts shipped hacks 27.9% → 14.6% (CI −23.3 to −4.6 points).

## Mechanical checks

New test [`tests/test_doc_links.py`](../tests/test_doc_links.py) covers `README.md`, `REPORT.md`,
`PITCH.md` and `docs/*.md`. It checks every relative Markdown link and image, reference-style
definitions, HTML `<img>`, `<a>` and `<source>` targets, and `#anchor` fragments against GitHub-style
heading slugs. It ignores code blocks and inline code. It fails on any missing file or heading. The
older `tests/test_md_links.py` checks only that link targets exist, for all `*.md` files.

**Result at `836dab5`: no broken links, images or anchors** in README, REPORT, PITCH or any `docs/*.md`.
There was nothing to fix in `docs/`.

**Not links, but dead paths (for the owners).** These are inline-code paths, not links, so the test
doesn't cover them:
- `docs/claims_audit.md:116,140,241-244,260,286,346` cite `results/judge_validation/SUMMARY.md`,
  which does not exist. Not edited: `claims_audit.md` is out of scope.
- `docs/repro_check.md:172,224,311` name `results/MITIGATION_bestofn.md`,
  `results/probe_v1/RESULTS.md` and `results/errors_v2_corrected/sample.json`. These are
  intentional: they are outputs that the documented commands write or used to write.

**README, REPORT, PITCH:** no broken relative links or images.
