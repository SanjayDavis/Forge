"""Tiny stdlib-only web UI for a Forge project.

Serves a single-page app that visualises the task graph: status columns,
ready highlighting, progress, and a detail panel. No build step, no
dependencies — just `forge -d <project> serve`.
"""

from __future__ import annotations

import http.server
import json
import socketserver
import threading
import webbrowser
from typing import Any

from .model import STATUS_DONE, STATUS_IN_PROGRESS, STATUS_NEEDS_REVISION, STATUS_TODO


def _task_payload(k) -> dict:
    g = k.graph
    tasks = []
    for t in sorted(g.tasks.values(), key=lambda x: x.created_seq):
        tasks.append({
            "id": t.id,
            "title": t.title,
            "description": t.description,
            "status": t.effective_status(g.tasks),
            "priority": t.priority,
            "acceptance": list(t.acceptance),
            "files": list(t.files),
            "notes": list(t.notes),
            "depends_on": list(t.depends_on),
            "composite": t.composite,
            "evidence": [{"kind": e.kind, "source": e.source, "detail": e.detail}
                         for e in t.evidence],
            "last_failure": t.last_failure,
        })
    ready = list(k.ready())
    nxt = k.next()
    progress = k.progress()
    return {
        "tasks": tasks,
        "ready": ready,
        "next": nxt,
        "progress": progress,
        "roots": [r.id for r in g.roots()],
    }


_HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Forge — Task Board</title>
<style>
  :root { --bg:#0f1115; --panel:#171a21; --card:#1f232d; --border:#2a2f3a;
          --text:#e6e8ec; --muted:#9aa3b2; --accent:#6ea8fe; --done:#3fb950;
          --ip:#d29922; --rev:#f85149; --todo:#8b949e; --ready:#58a6ff; }
  * { box-sizing:border-box; }
  body { margin:0; font-family:ui-sans-serif,system-ui,-apple-system,Segoe UI,Roboto,sans-serif;
         background:var(--bg); color:var(--text); }
  header { padding:16px 24px; border-bottom:1px solid var(--border); display:flex;
           align-items:center; gap:16px; }
  header h1 { margin:0; font-size:18px; }
  header .meta { color:var(--muted); font-size:13px; }
  .progress { flex:1; max-width:360px; }
  .progress .bar { height:8px; background:#2a2f3a; border-radius:4px; overflow:hidden; }
  .progress .fill { height:100%; background:var(--done); transition:width .3s; }
  .progress .label { font-size:12px; color:var(--muted); margin-top:4px; }
  main { display:grid; grid-template-columns: 1fr 360px; gap:16px; padding:16px 24px; }
  .board { display:grid; grid-template-columns: repeat(4, 1fr); gap:12px; }
  .col { background:var(--panel); border-radius:8px; padding:10px; min-height:200px; }
  .col h2 { margin:0 0 8px; font-size:13px; color:var(--muted); text-transform:uppercase;
            letter-spacing:.05em; display:flex; justify-content:space-between; }
  .col h2 .count { background:#2a2f3a; padding:2px 8px; border-radius:10px; font-size:11px; }
  .card { background:var(--card); border:1px solid var(--border); border-radius:6px;
          padding:10px; margin-bottom:8px; cursor:pointer; transition:border-color .15s; }
  .card:hover { border-color:var(--accent); }
  .card.ready { border-color:var(--ready); box-shadow:0 0 0 1px var(--ready) inset; }
  .card .title { font-size:13px; font-weight:600; }
  .card .id { font-size:11px; color:var(--muted); font-family:ui-monospace,monospace; }
  .card .prio { font-size:10px; padding:1px 6px; border-radius:8px; background:#2a2f3a;
                color:var(--muted); margin-left:6px; }
  .card .prio.high { background:#3a1f1f; color:#ff7b72; }
  .card .deps { font-size:11px; color:var(--muted); margin-top:4px; }
  .detail { background:var(--panel); border-radius:8px; padding:16px; position:sticky;
            top:16px; max-height:calc(100vh - 32px); overflow:auto; }
  .detail h3 { margin:0 0 8px; }
  .detail .row { margin:8px 0; }
  .detail .label { color:var(--muted); font-size:11px; text-transform:uppercase; }
  .detail ul { margin:4px 0 0 18px; padding:0; }
  .detail .empty { color:var(--muted); font-style:italic; }
  .legend { display:flex; gap:12px; font-size:12px; color:var(--muted); }
  .dot { display:inline-block; width:8px; height:8px; border-radius:50%; margin-right:4px; }
  footer { padding:12px 24px; color:var(--muted); font-size:12px; border-top:1px solid var(--border); }
  @media (max-width:900px){ main{grid-template-columns:1fr;} .board{grid-template-columns:repeat(2,1fr);} }
</style>
</head>
<body>
<header>
  <h1>Forge Task Board</h1>
  <div class="legend">
    <span><span class="dot" style="background:var(--todo)"></span>todo</span>
    <span><span class="dot" style="background:var(--ip)"></span>in progress</span>
    <span><span class="dot" style="background:var(--rev)"></span>needs revision</span>
    <span><span class="dot" style="background:var(--done)"></span>done</span>
    <span><span class="dot" style="background:var(--ready)"></span>ready</span>
  </div>
  <div class="progress">
    <div class="bar"><div class="fill" id="fill" style="width:0%"></div></div>
    <div class="label" id="plabel">loading…</div>
  </div>
</header>
<main>
  <div class="board" id="board"></div>
  <aside class="detail" id="detail"><div class="empty">Select a task to see details.</div></aside>
</main>
<footer>Auto-refreshes every 3s. Data from <code>events.log</code> via the Forge kernel.</footer>
<script>
const STATUSES = ["todo","in_progress","needs_revision","done"];
const COLORS = {todo:"var(--todo)",in_progress:"var(--ip)",needs_revision:"var(--rev)",done:"var(--done)"};
let DATA = null, SELECTED = null;
function esc(s){ return String(s).replace(/[&<>"']/g, c=>({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[c])); }
async function load(){
  const r = await fetch('/api/data'); DATA = await r.json();
  render();
}
function render(){
  const board = document.getElementById('board');
  board.innerHTML = '';
  const byStatus = Object.fromEntries(STATUSES.map(s=>[s,[]]));
  DATA.tasks.forEach(t=>{ (byStatus[t.status]||byStatus.todo).push(t); });
  STATUSES.forEach(s=>{
    const col = document.createElement('div'); col.className='col';
    const h = document.createElement('h2');
    h.innerHTML = s.replace('_',' ') + ' <span class="count">'+byStatus[s].length+'</span>';
    col.appendChild(h);
    byStatus[s].forEach(t=>{
      const card = document.createElement('div');
      const ready = DATA.ready.includes(t.id);
      card.className = 'card' + (ready?' ready':'');
      card.onclick = ()=>{ SELECTED=t.id; renderDetail(); };
      card.innerHTML = '<div class="title">'+esc(t.title)+'<span class="prio '+t.priority+'">'+t.priority+'</span></div>'
        + '<div class="id">'+esc(t.id)+'</div>'
        + (t.depends_on.length?'<div class="deps">depends on: '+t.depends_on.map(esc).join(', ')+'</div>':'');
      col.appendChild(card);
    });
    board.appendChild(col);
  });
  const p = DATA.progress;
  const pct = p.total? Math.round(100*p.done/p.total):0;
  document.getElementById('fill').style.width = pct+'%';
  document.getElementById('plabel').textContent = 'done '+p.done+'/'+p.total+' ('+pct+'%) · ready: '+(DATA.ready.join(', ')||'none')+' · next: '+(DATA.next||'—');
  renderDetail();
}
function renderDetail(){
  const el = document.getElementById('detail');
  if(!SELECTED || !DATA){ el.innerHTML='<div class="empty">Select a task to see details.</div>'; return; }
  const t = DATA.tasks.find(x=>x.id===SELECTED);
  if(!t){ el.innerHTML='<div class="empty">Not found.</div>'; return; }
  let h = '<h3>'+esc(t.title)+'</h3>'
    + '<div class="row"><div class="label">id</div>'+esc(t.id)+'</div>'
    + '<div class="row"><div class="label">status</div>'+esc(t.status)+(DATA.ready.includes(t.id)?' (ready)':'')+'</div>'
    + '<div class="row"><div class="label">priority</div>'+esc(t.priority)+'</div>';
  if(t.description) h += '<div class="row"><div class="label">description</div>'+esc(t.description)+'</div>';
  if(t.acceptance.length){ h+='<div class="row"><div class="label">acceptance</div><ul>'+t.acceptance.map(a=>'<li>'+esc(a)+'</li>').join('')+'</ul></div>'; }
  if(t.files.length){ h+='<div class="row"><div class="label">files</div><ul>'+t.files.map(f=>'<li>'+esc(f)+'</li>').join('')+'</ul></div>'; }
  if(t.depends_on.length){ h+='<div class="row"><div class="label">depends on</div>'+t.depends_on.map(esc).join(', ')+'</div>'; }
  if(t.notes.length){ h+='<div class="row"><div class="label">notes</div><ul>'+t.notes.map(n=>'<li>'+esc(n)+'</li>').join('')+'</ul></div>'; }
  if(t.evidence.length){ h+='<div class="row"><div class="label">evidence</div><ul>'+t.evidence.map(e=>'<li>['+e.kind+'] '+esc(e.source)+' — '+esc(e.detail)+'</li>').join('')+'</ul></div>'; }
  if(t.last_failure) h+='<div class="row"><div class="label">last failure</div>'+esc(t.last_failure)+'</div>';
  el.innerHTML = h;
}
load();
setInterval(load, 3000);
</script>
</body>
</html>
"""


class _Handler(http.server.BaseHTTPRequestHandler):
    def __init__(self, *a, kernel=None, html=_HTML, **kw):
        self._kernel = kernel
        self._html = html
        super().__init__(*a, **kw)

    def do_GET(self):
        if self.path == "/" or self.path.startswith("/index"):
            data = self._html.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        elif self.path == "/api/data":
            payload = _task_payload(self._kernel)
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, *args):
        pass


def serve(kernel, host: str = "127.0.0.1", port: int = 8000,
          open_browser: bool = True) -> int:
    handler = lambda *a, **kw: _Handler(*a, kernel=kernel, **kw)
    class _Server(socketserver.TCPServer):
        allow_reuse_address = True
    httpd = _Server((host, port), handler)
    url = f"http://{host}:{port}/"
    print(f"Forge web UI: {url}  (Ctrl+C to stop)")
    if open_browser:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        httpd.server_close()
    return 0
