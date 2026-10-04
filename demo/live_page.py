"""``/live``: start a live run (subject agent + open-weight auditor on Modal) and list recent ones."""

from __future__ import annotations

import json
from urllib.parse import quote

from demo.pages import esc, shell

CONFIG_BLURB = {
    "honest": "plain instructions",
    "incentivized": "graded by eval score",
    "pressure": "career pressure to hit the target",
    "covert": "red-team: hack and hide it",
    "covert_monitored": "red-team, told a monitor is watching",
    "sycophantic_pi": "PI wants a particular result",
}

HEAD = """
.live-form{display:grid;grid-template-columns:repeat(3,minmax(0,1fr)) auto;gap:14px;align-items:end;margin:18px 0 26px}
.live-form label{display:flex;flex-direction:column;gap:6px;color:var(--dim);font-size:13px;text-transform:uppercase;letter-spacing:.05em}
.live-form select,.live-form input{background:#0d1119;color:var(--text);border:1px solid var(--line);border-radius:8px;padding:10px;font-size:15px}
.live-form button{background:var(--red);color:#fff;border:0;border-radius:8px;padding:12px 22px;font-weight:700;font-size:15px;cursor:pointer}
.live-form button:disabled{opacity:.5;cursor:wait}
.runs{width:100%;border-collapse:collapse}.runs td,.runs th{padding:8px 10px;border-bottom:1px solid var(--line);text-align:left}
.lede{color:var(--dim);max-width:900px;line-height:1.5}.err{color:var(--red)}
"""

SCRIPT = """
const form = document.getElementById("live-form"), btn = document.getElementById("go"), msg = document.getElementById("msg");
form.addEventListener("submit", async ev => {
  ev.preventDefault(); btn.disabled = true; msg.textContent = "Starting… (the GPU may take a minute to wake up)";
  const q = new URLSearchParams(new FormData(form));
  try {
    const r = await fetch("/api/live/start?" + q.toString()); const d = await r.json();
    if (!r.ok) throw new Error(d.error || r.statusText);
    location.href = d.view_url;
  } catch (e) { msg.textContent = "Could not start: " + e.message; msg.className = "err"; btn.disabled = false; }
});
async function refresh(){
  try {
    const runs = await (await fetch("/api/live/runs")).json(); const tb = document.getElementById("runs-body");
    tb.innerHTML = runs.length ? "" : '<tr><td colspan="6" style="color:var(--faint)">No live runs yet.</td></tr>';
    for (const r of runs){
      const tr = document.createElement("tr");
      const a = `<a href="${r.view_url}">${r.run_id}</a>`;
      tr.innerHTML = `<td>${a}</td><td>${r.subject_model}</td><td>${r.auditor_model}</td><td>${r.status}${r.error ? ' <span class="err">' + r.error.replace(/</g,"&lt;") + '</span>' : ""}</td><td>${r.interim_audits}</td><td>${r.verdict ?? ""}</td>`;
      tb.append(tr);
    }
  } catch (e) {}
}
refresh(); setInterval(refresh, 4000);
"""


def view_url(trajectory_key: str) -> str:
    return f"/view?traj={quote(trajectory_key)}&live=1"


def live_page(tasks: list[dict], configs: list[str], subjects: list[str], enabled: bool, open_model: str,
              need_code: bool) -> str:
    if not enabled:
        body = ('<h1>Run live</h1><p class="lede">Live runs are off. Start the demo with <code>--live-runs</code> and '
                '<code>PUNISH_VLLM_URL</code>/<code>PUNISH_VLLM_API_KEY</code> pointing at <code>live/vllm_server.py</code> '
                'on Modal.</p>')
        return shell("Run live", body, active="live", head=HEAD)
    task_opts = "".join(f'<option value="{esc(t["id"])}">{esc(t["id"])} - {esc(t.get("title") or "")}</option>' for t in tasks)
    cfg_opts = "".join(f'<option value="{esc(c)}"{" selected" if c == "covert" else ""}>{esc(c)} - {esc(CONFIG_BLURB.get(c, ""))}</option>'
                       for c in configs)
    labels = {"open": f"{open_model} (open weights, Modal GPU)", "claude": "Claude Sonnet 4.6 (Anthropic API)"}
    subj_opts = "".join(f'<option value="{s}">{esc(labels.get(s, s))}</option>' for s in subjects)
    code = '<label>Passcode<input name="code" type="password" autocomplete="off"></label>' if need_code else ""
    body = f"""
<h1>Run live</h1>
<p class="lede">A subject agent gets a science task with a planted exploit (a leaked grader, a cached answer, a convenient
subset...) and works on it with real sandboxed <code>read_file</code> / <code>run_python</code> / <code>write_report</code>
tools. While it works, an <b>open-weight auditor ({esc(open_model)}) running on a Modal GPU</b> reads its private
reasoning and tool calls and posts flags to the right-hand feed. When the report is written, it gives a final verdict
in all three visibility modes.</p>
<form class="live-form" id="live-form">
  <label>Task<select name="task">{task_opts}</select></label>
  <label>Agent prompt<select name="config">{cfg_opts}</select></label>
  <label>Subject model<select name="subject">{subj_opts}</select></label>
  {code}
  <button id="go" type="submit">Run live ▶</button>
</form>
<p id="msg" class="lede"></p>
<h2>Recent live runs</h2>
<table class="runs"><thead><tr><th>Run</th><th>Subject</th><th>Auditor</th><th>Status</th><th>Live audits</th><th>Verdict</th></tr></thead>
<tbody id="runs-body"></tbody></table>
<script>window.__punishLive = {json.dumps({"subjects": subjects})};</script>
"""
    return shell("Run live", body, active="live", head=HEAD, script=SCRIPT)
