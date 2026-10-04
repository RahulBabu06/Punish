# Related work

Every source below was opened and read while this note was being written. The numbers quoted
come from those pages. Each entry ends with a short **Punish:** line saying how the project
relates to it.

## 1. Reward hacking and specification gaming

- **Amodei, Olah, Steinhardt, Christiano, Schulman, Mané. *Concrete Problems in AI Safety*.**
  arXiv:1606.06565, 2016. <https://arxiv.org/abs/1606.06565>
  Lists "reward hacking" as one of five practical accident-risk problems that come from a
  wrong objective function.
  **Punish:** each task is a small reward-hacking environment. The grader (an `eval.py` answer
  key, an R² threshold, a "p < 0.05" sponsor note, a plain-accuracy check) is a flawed proxy
  for the real objective, which is an honest analysis.

- **Krakovna et al. (DeepMind). *Specification gaming: the flip side of AI ingenuity*.** 2020.
  <https://deepmind.google/blog/specification-gaming-the-flip-side-of-ai-ingenuity/>
  Defines specification gaming as behaviour that satisfies the literal objective without
  achieving the intended outcome.
  **Punish:** our six planted exploits are specification-gaming opportunities from scientific
  practice (p-hacking, metric swapping, citation padding), not from games or robotics.

- **Skalse, Howe, Krasheninnikov, Krueger. *Defining and Characterizing Reward Hacking*.**
  NeurIPS 2022, arXiv:2209.13085. <https://arxiv.org/abs/2209.13085>
  Formal definition: a proxy is hackable if raising the proxy reward can lower the true reward.
  **Punish:** every task's `exploit` field states a proxy that a hacked report can max out
  while being worse on the true objective. `honest_solution` gives the true-objective answer.

- **Denison et al. (Anthropic). *Sycophancy to Subterfuge: Investigating Reward Tampering in
  Language Models*.** arXiv:2406.10162, 2024. <https://arxiv.org/abs/2406.10162>,
  <https://www.anthropic.com/research/reward-tampering>
  Shows that training on a curriculum of easy-to-game environments (sycophancy, checklist
  manipulation) generalises zero-shot to rewriting the model's own reward function.
  **Punish:** gives the motivation for detecting small integrity violations (an unread grader
  value, a quietly dropped site) before an RL loop rewards them.

- **Anthropic. *From shortcuts to sabotage: natural emergent misalignment from reward
  hacking*.** 2025. <https://www.anthropic.com/research/emergent-misalignment-reward-hacking>
  Reports that models which learn to reward-hack in real production coding environments go on
  to show broader misaligned behaviour, including alignment faking and sabotage of AI safety
  research (in 12% of runs of their sabotage evaluation, the model tried to sabotage the code).
  **Punish:** same motivation as above. An auditor that catches the hack in the trajectory
  could give the signal needed to patch an environment before the behaviour spreads.

- **Bondarenko, Volk, et al. (Palisade Research). *Demonstrating specification gaming in
  reasoning models*.** 2025.
  <https://palisaderesearch.org/research/specification-gaming>
  Reasoning models (o1-preview, DeepSeek R1) often hack a chess-engine benchmark by default,
  while language models such as GPT-4o and Claude 3.5 Sonnet need to be nudged before they hack.
  **Punish:** similar to our early observation that Sonnet 4.6 rarely hacks unless the `covert`
  prompt tells it to, while Haiku 4.5 and Sonnet 4.5 hack readily when told to (see
  `REPORT.md` §7.4).

## 2. Reward hacking measured in frontier agents

- **METR. *Recent Frontier Models Are Reward Hacking*.** June 2025.
  <https://metr.org/blog/2025-06-05-recent-reward-hacking/>
  Records o3 and other frontier agents monkey-patching evaluators, reading leaked reference
  solutions, and overwriting timers. o3 reward-hacks in 0.7% of HCAST runs, and far more often
  on some RE-Bench tasks.
  **Punish:** `leaked_answer` (the expected p-value sits in `eval.py`) is a direct
  scientific-analysis version of METR's "leaked solution" and "tampered scorer" cases.

- **Zhong, Raghunathan, Carlini. *ImpossibleBench: Measuring LLMs' Propensity of Exploiting
  Test Cases*.** arXiv:2510.20270, 2025. <https://arxiv.org/abs/2510.20270>
  Builds "impossible" versions of LiveCodeBench and SWE-bench where the tests contradict the
  spec, so any pass counts as cheating. GPT-5 cheats on 76% of Oneoff-SWEbench tasks and 2.9% of
  Oneoff-LiveCodeBench tasks. LLM monitors catch 86–89% of cheating on LiveCodeBench but only
  42–65% on SWE-bench.
  **Punish:** we use the same design idea (any "pass" requires breaking the spec) in a science
  setting. For example, R² ≥ 0.90 is unreachable honestly when the full-data R² is about 0.447.
  The drop in monitor performance on harder tasks is why we report auditor quality per task.

## 3. Chain-of-thought monitoring

- **Baker, Huizinga, Gao, Dou, Guan, Madry, Zaremba, Pachocki, Farhi (OpenAI). *Monitoring
  Reasoning Models for Misbehavior and the Risks of Promoting Obfuscation*.**
  arXiv:2503.11926, 2025. <https://arxiv.org/abs/2503.11926>; blog:
  <https://openai.com/index/chain-of-thought-monitoring/>
  A GPT-4o monitor that reads o3-mini's CoT together with its actions catches reward hacks in
  agentic coding much better than an actions-only monitor. A weaker model can monitor a
  stronger one. But adding a CoT monitor to the RL reward, with enough optimisation, produces
  *obfuscated* reward hacking, so the authors recommend paying a "monitorability tax".
  **Punish:** our auditor modes copy their comparison. `full_trace` corresponds to their
  CoT + actions monitor, `report_only` (no reasoning) to their action monitor, and
  `final_report` is an output-only baseline below both. We use the auditor for evaluation
  only and never as a training reward, which follows their warning.

- **Chen et al. (Anthropic Alignment Science). *Reasoning Models Don't Always Say What They
  Think*.** arXiv:2505.05410, 2025. <https://arxiv.org/abs/2505.05410>; blog:
  <https://www.anthropic.com/research/reasoning-models-dont-say-think>
  Inserts hints into prompts and checks whether the CoT admits using them. Claude 3.7 Sonnet
  mentions the hint about 25% of the time and DeepSeek R1 about 39%. For the "unauthorized
  access" hint, the figures are 41% and 19%. In synthetic RL environments with planted reward
  hacks, Claude 3.7 Sonnet learns the hack (reward > 0.99) but verbalises it in under 2% of
  examples in 5 of 6 environments.
  **Punish:** this is why the auditor does not depend on reasoning alone. Tool calls and
  tool results (which files were read, what code ran, what it printed) are the evidence a
  model cannot leave out, and `report_only` measures how much the auditor can do with only
  that evidence.

- **Korbak, Balesni, et al. (multi-lab position paper). *Chain of Thought Monitorability: A New and
  Fragile Opportunity for AI Safety*.** arXiv:2507.11473, 2025.
  <https://arxiv.org/abs/2507.11473>
  Argues that CoT monitoring is imperfect but valuable, that monitorability can be lost
  through training choices, and that developers should track it.
  **Punish:** the `full_trace − report_only` gap is a small, task-specific monitorability
  measure for science agents.

- **Emmons, Jenner, et al. (Google DeepMind). *When Chain of Thought is Necessary, Language
  Models Struggle to Evade Monitors*.** arXiv:2507.05246, 2025. <https://arxiv.org/abs/2507.05246>
  Distinguishes CoT-as-rationalisation from CoT-as-computation and finds monitors work best
  when the bad behaviour needs serial reasoning.
  **Punish:** our planted exploits need very little reasoning (copying 0.312 from a file takes
  one step). That is the hard case for CoT monitoring, and it is why `report_only` stays
  competitive in our data.

- **Arnav, Bernabeu-Pérez, Helm-Burger, Kostolansky, Whittingham, Phuong. *CoT Red-Handed:
  Stress Testing Chain-of-Thought Monitoring*.** arXiv:2505.23575, 2025.
  <https://arxiv.org/abs/2505.23575>
  In a red-team setup where a model is told to do a hidden side task, CoT monitoring beats
  action-only monitoring on subtle sabotage, but can add noise on obvious sabotage, where the
  reasoning can mislead the monitor. A hybrid monitor that scores reasoning and actions
  separately does best.
  **Punish:** our `covert` config is the same kind of instructed model organism. Their result
  suggests a future auditor mode that scores reasoning and actions separately and combines the
  scores.

- **Turpin, Arditi, Li, Benton, Michael. *Teaching Models to Verbalize Reward Hacking in
  Chain-of-Thought Reasoning*.** arXiv:2506.22777, 2025. <https://arxiv.org/abs/2506.22777>
  Verbalization fine-tuning (VFT) teaches models to say when they are using prompt cues. In
  their setup, the share of undetected reward hacks falls from 88% to 6%.
  **Punish:** an auditor like ours is the downstream consumer of verbalised hacks. VFT would
  raise the ceiling of `full_trace` relative to `report_only`.

## 4. Scheming, sandbagging and auditing

- **Meinke, Schoen, Scheurer, Balesni, Shah, Hobbhahn (Apollo Research). *Frontier Models are
  Capable of In-context Scheming*.** arXiv:2412.04984, 2024. <https://arxiv.org/abs/2412.04984>
  o1, Claude 3.5 Sonnet, Claude 3 Opus, Gemini 1.5 Pro and Llama 3.1 405B all scheme in
  context: they add subtle mistakes, try to disable oversight, and try to exfiltrate weights.
  o1 keeps up the deception in over 85% of follow-up questions.
  **Punish:** `covert` is a deliberately prompted in-context schemer ("hide the shortcut in your
  visible output"). Our `trace_claim_mismatch` hack type is the auditing version of their
  "covert action" label.

- **Schoen et al. (Apollo Research & OpenAI). *Stress Testing Deliberative Alignment for
  Anti-Scheming Training*.** arXiv:2509.15541, 2025. <https://arxiv.org/abs/2509.15541>
  Across 26 out-of-distribution evaluations (180+ environments), deliberative alignment cuts
  covert-action rates from 13% to 0.4% (o3) and from 8.7% to 0.3% (o4-mini) without removing
  them.
  **Punish:** a reminder that low hack rates under `honest` prompts do not mean the hack rate
  is zero.

- **van der Weij, Hofstätter, Jaffe, Brown, Ward. *AI Sandbagging: Language Models can
  Strategically Underperform on Evaluations*.** arXiv:2406.07358, 2024.
  <https://arxiv.org/abs/2406.07358>
  Frontier models can be prompted or fine-tuned to underperform selectively on
  dangerous-capability evals while keeping general performance.
  **Punish:** we look for the opposite failure (claiming more than was achieved), but the
  threat model is the same: the visible output is not reliable evidence of what the model did
  or can do.

- **Kutasov et al. *SHADE-Arena: Evaluating Sabotage and Monitoring in LLM Agents*.**
  arXiv:2506.15740, 2025. <https://arxiv.org/abs/2506.15740>
  Paired main tasks and hidden side tasks for agents, plus a monitor. The best sabotage agent
  (Claude 3.7 Sonnet) scores 27%. The best monitor (Gemini 2.5 Pro) reaches AUC 0.87. Side-task
  success depends heavily on a hidden scratchpad that the monitor cannot see.
  **Punish:** same agent-plus-monitor structure, applied to scientific analysis. Their
  hidden-scratchpad ablation is what our `report_only` mode does.

- **Marks et al. (Anthropic). *Auditing Language Models for Hidden Objectives*.**
  arXiv:2503.10965, 2025. <https://arxiv.org/abs/2503.10965>
  A blind auditing game: teams try to find a hidden reward-model-sycophancy objective that was
  deliberately trained into a model.
  **Punish:** we use the same "model organism with a known planted behaviour" method. Our
  organism is prompted (`covert`) rather than trained, and we audit single trajectories rather
  than the model itself.

## 5. Integrity of AI scientists

- **Sakana AI. *The AI Scientist: Towards Fully Automated Open-Ended Scientific Discovery*.**
  arXiv:2408.06292, 2024. <https://sakana.ai/ai-scientist/>, <https://arxiv.org/abs/2408.06292>
  An end-to-end LLM pipeline that generates ideas, runs experiments, and writes papers. The
  authors report that the system sometimes edited its own experiment script, for example to
  relaunch itself or to extend its timeout, instead of making the code faster.
  **Punish:** this is the failure we audit for. A science agent changes the conditions of its
  own evaluation, and only the trajectory shows it.

- **Beel, Kan, Baumgart. *Evaluating Sakana's AI Scientist: Bold Claims, Mixed Results, and a
  Promising Future?*** arXiv:2502.14297, 2025. <https://arxiv.org/abs/2502.14297>
  An independent evaluation. 5 of 12 proposed experiments (42%) failed because of coding
  errors. Several runs that finished produced logically flawed or misleading results.
  **Punish:** the manuscripts looked fine on the surface and the problems only showed up when
  someone checked the work. That supports auditing what the agent actually did, not just the
  report (`final_report` mode is our measure of a report-only review).

- **Walters & Wilder. *Fabrication and errors in the bibliographic citations generated by
  ChatGPT*.** Scientific Reports 13, 14045 (2023).
  <https://www.nature.com/articles/s41598-023-41032-5>
  In literature reviews written by ChatGPT, 55% of GPT-3.5 citations and 18% of GPT-4
  citations were fabricated.
  **Punish:** motivates the `fake_citation` task and the `fabricated_source` hack type. Our
  probe adds a subtler version: real bibliography entries cited for claims they do not support
  (see `REPORT.md` §7.3).
