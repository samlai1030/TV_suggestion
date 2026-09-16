#!/usr/bin/env python3
"""Build a static snapshot of the TV suggestions dashboard and push it to
samlai1030/TV_suggestion via the GitHub Contents API."""
import base64
import json
import sys
import urllib.request
import urllib.error

sys.path.insert(0, "/opt/hatch/skills/skill-creator/bin")
from dynamic_credentials import add_surrogate_to_request, read_json_response

API = "https://api.github.com"
REPO = "samlai1030/TV_suggestion"

SECTIONS = [
    ("featured", "本週精選"),
    ("movies", "熱門電影"),
    ("series", "熱門影集"),
    ("taiwan", "台灣焦點"),
]


def api(path, method="GET", payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(API + path, data=data, method=method, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": "tony-assistant",
        "Content-Type": "application/json",
    })
    add_surrogate_to_request(req, "custom.github", entry_name="access_token",
                             allowed_hosts=["api.github.com"])
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return read_json_response(resp)
    except urllib.error.HTTPError as e:
        print(f"HTTP {e.code} on {method} {path}: {e.read().decode()[:300]}",
              file=sys.stderr)
        raise


def put_file(path, content, message):
    body = {"message": message,
            "content": base64.b64encode(content.encode("utf-8")).decode()}
    try:
        cur = api(f"/repos/{REPO}/contents/{path}")
        body["sha"] = cur["sha"]
    except urllib.error.HTTPError as e:
        if e.code != 404:
            raise
    res = api(f"/repos/{REPO}/contents/{path}", method="PUT", payload=body)
    return res["content"]["html_url"]


def render_html(catalog):
    data_json = json.dumps(catalog, ensure_ascii=False)
    section_names = json.dumps(dict(SECTIONS), ensure_ascii=False)

    tpl = """<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>本週影視推薦 · TV Suggestion</title>
<style>
  :root { --bg:#0d0d12; --card:#16161e; --line:#26262f; --txt:#f2f0ea;
           --muted:#a8a29a; --gold:#d9a441; --red:#c0392b; }
  * { box-sizing:border-box; margin:0; padding:0; }
  body { background:var(--bg); color:var(--txt);
         font-family:"PingFang TC","Microsoft JhengHei","Noto Sans TC",sans-serif;
         padding:24px 16px 64px; }
  .wrap { max-width:1180px; margin:0 auto; }
  header { border-bottom:3px solid var(--gold); padding-bottom:16px; margin-bottom:20px; }
  header h1 { font-size:28px; letter-spacing:2px; }
  header h1 span { color:var(--gold); }
  header p { color:var(--muted); margin-top:8px; font-size:14px; }
  nav.filters { display:flex; gap:10px; flex-wrap:wrap; margin-bottom:24px; }
  nav.filters button { background:var(--card); color:var(--txt); border:1px solid var(--line);
    border-radius:999px; padding:8px 18px; font-size:14px; cursor:pointer; }
  nav.filters button.active { background:var(--gold); color:#111; border-color:var(--gold);
    font-weight:700; }
  .grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(300px,1fr)); gap:18px; }
  .card { background:var(--card); border:1px solid var(--line); border-radius:12px;
    overflow:hidden; display:flex; flex-direction:column; }
  .poster { aspect-ratio:16/9; background:#0a0a0e; display:flex; align-items:center;
    justify-content:center; overflow:hidden; }
  .poster img { width:100%; height:100%; object-fit:cover; }
  .poster .ph { color:var(--gold); font-size:20px; letter-spacing:4px; opacity:.7;
    padding:0 16px; text-align:center; }
  .body { padding:16px; display:flex; flex-direction:column; gap:8px; flex:1; }
  .body h2 { font-size:19px; }
  .body h2 .en { display:block; font-size:12px; color:var(--muted); font-weight:400; margin-top:2px; }
  .meta { font-size:12px; color:var(--muted); }
  .rating { display:inline-block; background:var(--gold); color:#111; font-weight:700;
    font-size:12px; border-radius:6px; padding:2px 8px; margin-right:6px; }
  .brief { font-size:14px; line-height:1.7; }
  .evidence { font-size:12px; color:var(--muted); border-left:2px solid var(--gold);
    padding-left:8px; }
  .plats { display:flex; gap:6px; flex-wrap:wrap; }
  .plat { font-size:12px; border:1px solid var(--gold); color:var(--gold);
    border-radius:6px; padding:2px 8px; }
  .warn { font-size:12px; color:#e8b34b; }
  .src { margin-top:auto; font-size:12px; }
  .src a { color:var(--muted); }
  footer { margin-top:40px; color:var(--muted); font-size:12px; text-align:center; }
  .sec-title { grid-column:1/-1; font-size:20px; color:var(--gold); letter-spacing:2px;
    margin:12px 0 2px; border-bottom:1px solid var(--line); padding-bottom:8px; }
</style>
</head>
<body>
<div class="wrap">
  <header>
    <h1>本週影視推薦 <span>· TV Suggestion</span></h1>
    <p>資料更新：__UPDATED__ ｜ 每週精選 · 熱門電影 · 熱門影集 · 台灣焦點 ｜ 共 __TOTAL__ 部</p>
  </header>
  <nav class="filters" id="filters"></nav>
  <main class="grid" id="grid"></main>
  <footer>靜態快照版本 · 完整互動版儀表板由 Tony 每週更新</footer>
</div>
<script>
const DATA = __DATA__;
const SECTIONS = __SECTIONS__;
const grid = document.getElementById('grid');
const nav = document.getElementById('filters');
let active = 'all';

function esc(s) {
  return String(s ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;')
    .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function card(it) {
  const meta = [it.year, it.format, it.origin, ...(it.genres||[])].filter(Boolean).join(' · ');
  const poster = it.poster_url
    ? '<img src="' + esc(it.poster_url) + '" alt="' + esc(it.title_zh) + '" loading="lazy" onerror="this.outerHTML=\'<div class=ph>' + esc(it.title_zh) + '</div>\'">'
    : '<div class="ph">' + esc(it.title_zh) + '</div>';
  const rating = it.rating ? '<span class="rating">★ ' + esc(it.rating) + (it.rating_source ? ' / ' + esc(it.rating_source) : '') + '</span>' : '';
  const plats = (it.platforms_tw||[]).map(p=>'<span class="plat">' + esc(p) + '</span>').join('');
  const warn = it.availability_note ? '<div class="warn">⚠ ' + esc(it.availability_note) + '</div>' : '';
  const ev = it.evidence ? '<div class="evidence">' + esc(it.evidence) + '</div>' : '';
  return '<article class="card">'
    + '<div class="poster">' + poster + '</div>'
    + '<div class="body">'
    + '<h2>' + esc(it.title_zh) + '<span class="en">' + esc(it.title_en||'') + '</span></h2>'
    + '<div class="meta">' + rating + esc(meta) + '</div>'
    + '<p class="brief">' + esc(it.brief_zh) + '</p>'
    + ev
    + '<div class="plats">' + plats + '</div>'
    + warn
    + '<div class="src"><a href="' + esc(it.source_url) + '" target="_blank" rel="noopener">來源：' + esc(it.source_name) + '</a></div>'
    + '</div></article>';
}

function render() {
  const items = DATA.items.filter(it => active==='all' || it.section===active);
  let html = '';
  if (active==='all') {
    for (const key of Object.keys(SECTIONS)) {
      const sec = items.filter(it=>it.section===key);
      if (!sec.length) continue;
      html += '<div class="sec-title">' + SECTIONS[key] + '</div>' + sec.map(card).join('');
    }
  } else {
    html = items.map(card).join('');
  }
  grid.innerHTML = html || '<p style="color:#a8a29a">這個分類目前沒有項目。</p>';
  Array.from(nav.children).forEach(b=>b.classList.toggle('active', b.dataset.k===active));
}

function buildNav() {
  const counts = {};
  DATA.items.forEach(it=>counts[it.section]=(counts[it.section]||0)+1);
  const defs = [['all','全部 ('+DATA.items.length+')']];
  for (const k of Object.keys(SECTIONS)) defs.push([k, SECTIONS[k] + ' (' + (counts[k]||0) + ')']);
  nav.innerHTML = defs.map(([k,label])=>'<button data-k="'+k+'">'+label+'</button>').join('');
  nav.addEventListener('click', e=>{
    const b = e.target.closest('button'); if(!b) return;
    active = b.dataset.k; render();
  });
}

buildNav();
render();
</script>
</body>
</html>
"""
    return (tpl.replace("__DATA__", data_json)
               .replace("__SECTIONS__", section_names)
               .replace("__UPDATED__", catalog["updated_date"])
               .replace("__TOTAL__", str(len(catalog["items"]))))


def main():
    with open("/home/hatch/workspace/tv-suggestion-site/catalog.json",
              encoding="utf-8") as f:
        catalog = json.load(f)

    html = render_html(catalog)
    url = put_file("index.html", html,
                   f"Add dashboard snapshot ({catalog['updated_date']})")
    print("index.html ->", url)

    readme = f"""# TV_suggestion

每週影視推薦儀表板的靜態快照。完整互動版由 Tony 每週整理更新。

- `index.html`：{catalog['updated_date']} 的片單快照（{len(catalog['items'])} 部），直接用瀏覽器開啟即可瀏覽。
- 分類：本週精選 / 熱門電影 / 熱門影集 / 台灣焦點，每部附推薦理由與台灣可看平台。

線上互動版：由 Tony 維護的儀表板（每週更新）。
"""
    url = put_file("README.md", readme, "Update README for dashboard snapshot")
    print("README.md ->", url)


if __name__ == "__main__":
    main()
