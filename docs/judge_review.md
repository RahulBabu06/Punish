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

## Round 2: re-read at integration `b4daf84` (REPORT at `bdf1a91`)

Same 10-minute path, now README → headline figure → PITCH → REPORT abstract and Conclusions →
`docs/slides.html` → `docs/SUBMISSION.md`. README/PITCH/SUBMISSION line numbers are at `b4daf84`, before this
branch's edits; REPORT line numbers are at `bdf1a91`, after `devin/report-polish` (merged here).

### Verdict

The first minute is now good. The figure is on line 6, the demo link on line 8, three takeaways and a
novelty paragraph follow, REPORT has a Conclusions section and no `TODO`s, and the label noise is gone
from README, PITCH and SUBMISSION. The new risk is the opposite of round 1. The robustness work was
honest, but it was bolted onto the headline: README takeaway 2, the core thesis, had grown to seven lines
with nine fractions from two cohorts, and "What to trust" (9 bullets) was longer than the takeaways. A
judge skimming takeaway 2 came away with "the trace doesn't help on natural hacks" rather than "the trace
exposes hacks the report hides". The remaining inconsistencies are on surfaces this branch doesn't own:
the slides, the FAQ and REPORT.

### Scorecard for the original 10 issues

| # | issue | status | what remains |
|---|---|---|---|
| 1 | Headline buried | **fixed** | Figure, demo link, takeaways and novelty fill the first screen (`README.md:1-31`). |
| 2 | Three label variants on every number | **partly fixed** | Fixed in README, PITCH, SUBMISSION and the REPORT abstract. Slides 5–7 and 9–10 still quote `leaked_answer`-excluded or original-label numbers (see new issue 4). |
| 3 | Same headline, different values | **partly fixed** | The stage script now matches figure panel B, and README/REPORT label the four cascade points as distinct. The FAQ still leads with a fifth cascade point, 64.3% / 5.4% (`docs/reviewer_faq.md:56,81`); Opus is 0.06 vs 0.12 FPR on slides 6 and 10 against 22.3% / 27.2% in the figure. |
| 4 | Over-claims vs Holm-corrected stats | **fixed** | PITCH and figure titles fixed. The new covert-only over-claim is new issue 5. |
| 5 | Novelty not stated | **fixed** | `README.md:27-31`, `docs/SUBMISSION.md:43-52`. |
| 6 | Demo friction | **fixed** | `docs/demo.html` linked at `README.md:8` and opens on `#/story`; `--story --open` is in the Quickstart. |
| 7 | `TODO(numbers)` in REPORT | **fixed** | None left in README, REPORT, PITCH or SUBMISSION. |
| 8 | Stale facts | **fixed** | "six tasks in the judged sweep (10 in the suite)", scoped "preliminary" status line, pytest described as the test dependency. |
| 9 | No conclusions; §8 too long | **partly fixed** | `## Conclusions` (`REPORT.md:912`) and a grouped Contents table (`REPORT.md:10-19`) now exist, but §8 still has 19 subsections and rubric v3 still sits inside §8.18 Task design (`REPORT.md:895`). |
| 10 | AI ground truth disclosed late | **fixed** | First "What to trust" bullet (`README.md:46-47`), SUBMISSION abstract and limitations. |

Score: 7 fixed, 3 partly fixed, 0 not fixed.

### New issues (ranked)

| # | issue | where | status |
|---|---|---|---|
| N1 | Robustness caveats bury the core thesis | `README.md:15-21,45-61` | fixed here |
| N2 | PITCH states the non-replicated v2 reversal as a finding | `PITCH.md:48,67,80` | fixed here |
| N3 | κ = 0.70 vs κ = 0.97 for the same judge check | `README.md:47`, `PITCH.md:90`, slide 9 vs `REPORT.md:826,956` | fixed in README/PITCH; slides listed |
| N4 | Slides and FAQ still on old label variants and a fifth cascade point | slides 5, 6, 7, 9, 10; `docs/reviewer_faq.md:56,81` | listed |
| N5 | REPORT headline and Conclusions miss the covert-only qualifier | `REPORT.md:44,918-919`; `docs/SUBMISSION.md:20-22` | SUBMISSION fixed; REPORT listed |

#### N1. The caveats bury the positive story (`README.md:15-21`, `45-61`)

Takeaway 2 mixed the claim, the v2 natural-hack split, the v3 replication and the demo run in one
seven-line sentence chain. The headline "The trace exposes instructed hacks, not natural ones" led with the
negative. "What to trust" then had three separate robustness bullets.

**Fix (done).**
- Takeaway 2 is now five lines and leads with the positive claim: "**The trace exposes instructed hacks
  the report hides.** With the agent's actions the auditor catches 0.91 of hacks against 0.74 from the
  final report alone. The gain comes from instructed (`covert`) hacks, 66 of the 93 positives, which the
  full trace catches at 0.97–0.98. [demo run] Natural hacks are harder (below)."
- The natural-hack numbers move to one "What to trust" bullet, "**Natural hacks are the weak spot.**",
  which keeps 19/27 = 0.70, 5/17 = 0.29, 26/27 vs 20/27 and the v3 non-replication (19/26 each,
  12/26 = 0.46).
- Config leak, clustered CIs and precision at prevalence merge into one "**Robustness**" bullet. Every
  number is unchanged and still checked by `tests/test_claims_audit.py`.

#### N2. PITCH says on stage what v3 doesn't replicate (`PITCH.md:48`)

The 1:40 beat says "on natural hacks the report alone did better", while PITCH's own note at line 11 says
"don't claim the report wins either". Q&A at line 80 also quotes 26/27 without the v3 result next to it.
And "the conclusions hold under all three" labels (line 67) over-claims: the false-positive cost of
seeing the actions disappears with `leaked_answer` excluded (FPR 0.21 in both modes, `SIGNIFICANCE.md`).

**Fix (done).**
- `PITCH.md:48`: "on natural hacks the actions didn't help." This is true on v2 and v3, and takes the
  same speaking time.
- `PITCH.md:80`: "and on v2 the report alone catches 26/27 (labeller-only v3: 19/26 either way, full-trace
  12/26 = 0.46)."
- `PITCH.md:67`: "The main conclusions hold under all three; the false-positive cost of seeing the actions
  does not (it comes from `leaked_answer`)."
- `PITCH.md:50`: "a quarter to a third" becomes "a fifth to a third". Opus `final_report` FPR is 0.20.

#### N3. Two κ values for one judge check

README, PITCH and slide 9 say κ = 0.70. REPORT §8.15 and §9 say the corrected judge has κ = 0.97. Both
are right (original vs corrected judge), but a judge who sees both suspects cherry-picking.

**Fix.**
- Done: README says "κ = 0.70; 0.97 after the correction those labels helped find", and PITCH says "κ = 0.70 (0.97 after the correction, which that check
  helped find)".
- For the slides owner, slide 9 "LLM ground truth" card (`docs/build_slides.py`): "Against 60 blind AI labels: κ 0.70
  (0.97 after the correction they helped find), never more lenient."

#### N4. Slides and FAQ lag the one-label rule (for their owners)

- **Slide 5, panel B note:** "With leaked_answer excluded: AUROC 0.962, recall 0.90, FPR 0.20." Replace
  with "Sonnet `full_trace`: recall 0.90 at FPR 0.34 (AUROC 0.891); the gain over the report is all on
  `covert` hacks."
- **Slide 6:** the big numbers are 0.06 / 0.12 (excluded). Use the corrected 0.22 / 0.27 to match figure
  panel B, or retitle to accuracy "+0.07 (Holm p = 0.002)" and drop the FPR tiles. Delete the "Original
  label (240 runs ...)" sentence.
- **Slide 7 title:** "46 of 91 found (leaked_answer excluded)" becomes "47 of 93 found (corrected label)", and
  likewise in the leaked_answer bullet.
- **Slide 9 "Small n":** drop "(original; 2–40 corrected)" and say "2–40 positives".
- **Slide 10 bullets 2–3:** replace "Opus FPR 0.06 vs 0.12 and recall 0.77 vs 0.63 with leaked_answer
  excluded" with "Opus accuracy +0.07 (Holm p = 0.002)", and "46 of the 91" with "47 of the 93".
- **`docs/reviewer_faq.md:56`:** replace "a cross-experiment heuristic→Sonnet point reaches 64.3% recall
  and 5.4% FPR" with "the heuristic→Sonnet cascade reaches 80.4% / 5.4% in-sample (76.8% / 5.4% with
  cross-fit thresholds) and 62.7% / 2.9% on held-out, labeller-only v3". In §9 (line 81), call 64.3%
  "the 5%-cap variant", not *the* cross-experiment point.

#### N5. REPORT's headline sentences miss the covert-only qualifier (for the REPORT owner)

The README, PITCH and SUBMISSION headlines now say the action gain is instructed-only. REPORT says it
only in a trailing sentence (`REPORT.md:61`) and in §9. A judge reading the abstract's numbered results or
the Conclusions gets the over-stated version.

**Fix.**
- `REPORT.md:44`: "2. **The trace exposes hacks the report hides.**" becomes "2. **The actions expose
  instructed hacks the report hides.**", and add after the AUROC list: "The recall gain is all on
  `covert` hacks (+0.33; −0.22 on natural hacks, which does not replicate on labeller-only v3)."
- `REPORT.md:918-919` (Conclusions bullet 3): "**Underpowered, covert-only recall gain; trajectory-wise
  FPR cost:** Sonnet actions-and-report recall is 0.91 versus 0.74 for report alone, all from `covert`
  hacks, but FPR is 0.35 versus 0.23."
- `REPORT.md:920-921` (bullet 4) reads as jargon. Suggested: "**Reasoning helps Opus, not Sonnet's
  verdicts:** Opus accuracy +0.071 (Holm p = 0.002, survives task resampling); Sonnet's flags don't
  change, though its ranking improves (AUROC +0.051)."
- §9 says the corrected judge has κ = 0.97 (`REPORT.md:956`). Add "(0.70 before the correction)" so it
  matches README.
- Done: SUBMISSION's abstract now says the full-trace vs final-report gap "comes from instructed hacks"
  (`docs/SUBMISSION.md:22`); the abstract stays within the 140–160 words its test requires.

### What to lead with (unchanged)

The three strengths from round 1 still hold, and the first screen now leads with them: the R² 0.447 → 0.92
replay, checkable rigour (paired Holm-corrected tests, the self-found label bug, byte-for-byte offline
reproduction, now plus clustered and v3 robustness checks), and the Opus / veto / natural-hacking findings.
The robustness checks are a strength when they sit one level down. Keep them out of the takeaways.
