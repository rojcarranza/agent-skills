# index.html - the single-page view of the guide

Loaded at phase 3, after the Markdown files are written. `.onboarding/index.html`
is one self-contained page that shows the whole guide at once: sidebar
navigation across README, flows, modules and reviewing PRs, cards, tables,
readable light and dark themes, and rendered diagrams. The Markdown files stay
the checked source; the page is the same content in a nicer frame.

`roj-explain-logic` reuses this contract for a PR brief:
`.pr-review/pr-<n>/brief.md` and `brief.html`, one `<section class="doc"
id="brief">`. Wherever this file says "the guide", read "the Markdown the page
is built from".

## Contents

- Contract
- Mapping from Markdown to HTML
- Page skeleton
- Check script
- Opening it

## Contract

- **Same content, no second investigation.** Build the page from the Markdown
  files you just wrote and verified. Never add a claim, diagram or anchor to
  the HTML that is not in the Markdown, and never drop one. If you correct
  something, correct the Markdown first and regenerate the section.
- **One file.** Inline CSS and JavaScript, no local assets, no web fonts, no
  framework. The only network reference is the Mermaid script below.
- **Mermaid from one pinned CDN version:**
  `https://cdn.jsdelivr.net/npm/mermaid@11.12.0/dist/mermaid.min.js`, with the
  `integrity` and `crossorigin` attributes shown in the skeleton. Never
  `@latest`, never a range, never another host.
- **Fallback.** Every diagram's Mermaid source is in the page as a readable
  code block. When the script does not load (blocked, offline, failed
  integrity check) or a diagram fails to render, that source stays visible
  and a one-line notice says so. A diagram never silently disappears.
- **Every `path:line` is a visible code reference:** `<code class="ref">`
  holding exactly the text the Markdown has (`path:line` or `path:line-line`).
- **Both themes readable.** Colours are CSS variables defined for light, for
  dark under `prefers-color-scheme`, and for the manual toggle. The page has
  an explicit background.
- **Reading, not an app.** Sections are all on the page, in order, so a
  reader can scroll the whole guide; navigation only jumps. No tabs that hide
  content, no JavaScript needed to read anything but the rendered diagrams.
- **Phone width works:** the sidebar becomes a top bar, tables scroll inside
  their own wrapper, nothing forces horizontal page scroll.

## Mapping from Markdown to HTML

| Markdown | HTML |
| --- | --- |
| each file | one `<section class="doc" id="readme">`, `id="flow-01-<slug>"`, `id="modules"`, `id="reviewing-prs"`, in that order, with the file's title as `<h2>`; any other file: `<section class="doc" id="<file stem>">` (`brief.md` is `id="brief"`) |
| the header `> Built from ...` lines | one `<p class="stamp">` each under the title, same words |
| `## N. Heading` | `<article class="card"><h3>N. Heading</h3>...</article>` |
| `### Heading` | `<h4>` inside the card |
| paragraph, list | `<p>`, `<ol>` or `<ul>`, inline `` `code` `` as `<code>` |
| `` `path:line` `` | `<code class="ref">path:line</code>` |
| table | `<div class="table-wrap"><table>...</table></div>` |
| a ```` ```mermaid ```` block | `<figure class="diagram"><div class="diagram-view"></div><pre class="diagram-src">escaped source</pre></figure>` |
| other fenced code (quotes of at most five lines) | `<pre class="code"><code>escaped</code></pre>` |
| `[?]` open question | `<li class="open">` |

Escape `&`, `<` and `>` in every diagram source and code block (`&amp;`,
`&lt;`, `&gt;`); the browser hands the original text back to Mermaid. Keep
the diagram source byte-for-byte except for that escaping.

Sidebar entries: one per section, plus the `<h3>` headings of the README as
nested links. Give every card an `id` so the links work.

## Page skeleton

Replace the `<!-- ... -->` comments and the sample content; keep the head, the
styles and the script as they are, adjusting only what the repository needs.

```html
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>TITLE</title>
<style>
  :root {
    --bg: #f7f7f5; --panel: #ffffff; --text: #1d2125; --muted: #5b6570;
    --line: #dcdfe3; --accent: #2457c5; --code-bg: #eef1f5; --warn-bg: #fff4d6;
  }
  @media (prefers-color-scheme: dark) {
    :root:not([data-theme="light"]) {
      --bg: #14171a; --panel: #1c2024; --text: #e6e8ea; --muted: #9aa5b1;
      --line: #2f353b; --accent: #7aa7ff; --code-bg: #262b31; --warn-bg: #3a3118;
    }
  }
  :root[data-theme="dark"] {
    --bg: #14171a; --panel: #1c2024; --text: #e6e8ea; --muted: #9aa5b1;
    --line: #2f353b; --accent: #7aa7ff; --code-bg: #262b31; --warn-bg: #3a3118;
  }
  * { box-sizing: border-box; }
  body { margin: 0; background: var(--bg); color: var(--text);
    font: 16px/1.6 system-ui, -apple-system, "Segoe UI", sans-serif; }
  .layout { display: grid; grid-template-columns: 17rem minmax(0, 1fr); min-height: 100vh; }
  nav.side { position: sticky; top: 0; align-self: start; height: 100vh; overflow-y: auto;
    padding: 1.25rem 1rem; border-right: 1px solid var(--line); background: var(--panel); }
  nav.side h1 { font-size: 1rem; margin: 0 0 .25rem; }
  nav.side a { display: block; padding: .2rem .5rem; color: var(--text); text-decoration: none;
    border-radius: 6px; overflow-wrap: anywhere; }
  nav.side a:hover { background: var(--code-bg); color: var(--accent); }
  nav.side a.sub { margin-left: 1rem; font-size: .9rem; color: var(--muted); }
  nav.side button { margin-top: 1rem; padding: .3rem .7rem; border: 1px solid var(--line);
    border-radius: 6px; background: var(--bg); color: var(--text); cursor: pointer; }
  main { padding: 1.5rem clamp(1rem, 4vw, 3rem) 4rem; min-width: 0; max-width: 62rem; }
  .doc { margin-bottom: 3rem; scroll-margin-top: 1rem; }
  .doc > h2 { font-size: 1.6rem; margin: 0 0 .25rem; }
  .stamp { color: var(--muted); font-size: .9rem; margin: 0 0 1rem; overflow-wrap: anywhere; }
  .card { background: var(--panel); border: 1px solid var(--line); border-radius: 10px;
    padding: 1rem 1.25rem; margin: 0 0 1rem; min-width: 0; scroll-margin-top: 1rem; }
  .card h3 { margin: 0 0 .5rem; font-size: 1.15rem; }
  code { background: var(--code-bg); padding: .1em .35em; border-radius: 4px;
    font: .9em ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; overflow-wrap: anywhere; }
  code.ref { color: var(--accent); border: 1px solid var(--line); white-space: nowrap; }
  pre { background: var(--code-bg); padding: .75rem 1rem; border-radius: 8px; overflow-x: auto;
    margin: .75rem 0; font: .85em/1.5 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }
  pre code { background: none; padding: 0; }
  .table-wrap { overflow-x: auto; margin: .75rem 0; }
  table { border-collapse: collapse; min-width: 100%; }
  th, td { border: 1px solid var(--line); padding: .4rem .6rem; text-align: left; vertical-align: top; }
  th { background: var(--code-bg); }
  figure.diagram { margin: 1rem 0; min-width: 0; }
  .diagram-view { overflow-x: auto; text-align: center; }
  .diagram-view svg { max-width: 100%; height: auto; }
  figure.rendered pre.diagram-src { display: none; }
  .diagram-note, #mermaid-banner { display: none; background: var(--warn-bg); border-radius: 6px;
    padding: .4rem .75rem; margin: 0 0 .5rem; font-size: .9rem; }
  figure.failed .diagram-note, #mermaid-banner.show { display: block; }
  li.open::marker { color: var(--accent); }
  @media (max-width: 860px) {
    .layout { display: block; }
    nav.side { position: static; height: auto; border-right: 0; border-bottom: 1px solid var(--line); }
  }
</style>
</head>
<body>
<div class="layout">
  <nav class="side" aria-label="Page sections">
    <h1>NAME</h1>
    <!-- one <a href="#readme"> per section, nested <a class="sub"> per README card -->
    <a href="#readme">README</a>
    <a class="sub" href="#readme-system-map">2. System map</a>
    <a href="#flow-01-slug">Flow: NAME</a>
    <a href="#modules">Modules</a>
    <a href="#reviewing-prs">Reviewing PRs</a>
    <button type="button" id="theme-toggle">Toggle theme</button>
  </nav>
  <main>
    <div id="mermaid-banner" role="status">Diagrams could not load from cdn.jsdelivr.net, so each one is shown as Mermaid source.</div>
    <section class="doc" id="readme">
      <h2>TITLE</h2>
      <p class="stamp">Built from commit <code>SHA</code> (DATE, branch <code>BRANCH</code>). Every claim cites <code>path:line</code>.</p>
      <!-- brief.html: the same stamp, then the intent and repo-map lines as <p class="stamp"> -->
      <article class="card" id="readme-system-map">
        <h3>2. System map</h3>
        <figure class="diagram">
          <div class="diagram-view"></div>
          <p class="diagram-note">This diagram could not be rendered, so its Mermaid source is shown.</p>
          <pre class="diagram-src">flowchart TD
  entry["main.go - wiring"] --&gt; svc["service/ - rules"]</pre>
        </figure>
        <ul><li><code class="ref">main.go:12</code> - the only wiring point.</li></ul>
      </article>
      <!-- the other README cards, in order -->
    </section>
    <!-- the flow sections, modules, reviewing-prs -->
  </main>
</div>
<script src="https://cdn.jsdelivr.net/npm/mermaid@11.12.0/dist/mermaid.min.js"
  integrity="sha384-o+g/BxPwhi0C3RK7oQBxQuNimeafQ3GE/ST4iT2BxVI4Wzt60SH4pq9iXVYujjaS"
  crossorigin="anonymous"></script>
<script>
(function () {
  var root = document.documentElement;
  try { var saved = localStorage.getItem("doc-theme"); if (saved) root.setAttribute("data-theme", saved); } catch (e) {}
  function theme() {
    return root.getAttribute("data-theme") ||
      (window.matchMedia && matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
  }
  var figures = Array.prototype.slice.call(document.querySelectorAll("figure.diagram"));
  var seq = 0;
  function draw() {
    if (!window.mermaid) {
      document.getElementById("mermaid-banner").className = "show";
      figures.forEach(function (fig) { fig.className = "diagram failed"; });
      return;
    }
    mermaid.initialize({ startOnLoad: false, securityLevel: "strict", theme: theme() === "dark" ? "dark" : "default" });
    figures.forEach(function (fig) {
      var src = fig.querySelector("pre.diagram-src").textContent;
      mermaid.render("diagram-" + (seq++), src).then(function (out) {
        fig.querySelector(".diagram-view").innerHTML = out.svg;
        fig.className = "diagram rendered";
      }).catch(function () { fig.className = "diagram failed"; });
    });
  }
  document.getElementById("theme-toggle").addEventListener("click", function () {
    var next = theme() === "dark" ? "light" : "dark";
    root.setAttribute("data-theme", next);
    try { localStorage.setItem("doc-theme", next); } catch (e) {}
    draw();
  });
  draw();
})();
</script>
</body>
</html>
```

The inline script sits after the CDN script on purpose: the browser runs them
in order, so by the time `draw()` runs `window.mermaid` either exists or the
load failed. Re-rendering on a theme change reads the source from the
`<pre>`, which is never edited.

## Check script

Compares the page against the Markdown. It fails when a diagram, a
`path:line` or a heading is in one and not the other, when the Mermaid script
is not pinned to an exact version, or when the fallback pieces are missing.
Save it to a scratch file outside the repository and run it with `python3`
(or `python` on Windows):

```
python3 check-html.py <ROOT>/.onboarding
python3 check-html.py <ROOT>/.pr-review/pr-<n> brief.html
```

With no page name the page is `index.html` and the Markdown is every `*.md`
under the folder. With a page name, the Markdown is the file with the same
stem (`brief.html` against `brief.md`), so other files in the folder, such as a
review report, are not compared.

`check-html.py`:

```python
import html, re, sys
from pathlib import Path

d = Path(sys.argv[1])
name = sys.argv[2] if len(sys.argv) > 2 else "index.html"
page = (d / name).read_text(encoding="utf-8")
mds = sorted(d.rglob("*.md")) if name == "index.html" else [d / (Path(name).stem + ".md")]
md = "\n".join(p.read_text(encoding="utf-8") for p in mds)

def norm(s):
    return "\n".join(line.rstrip() for line in s.strip().splitlines())

md_diagrams = sorted(norm(m) for m in re.findall(r"^```mermaid\n(.*?)^```$", md, re.M | re.S))
html_diagrams = sorted(norm(html.unescape(m)) for m in re.findall(
    r'<pre class="diagram-src">(.*?)</pre>', page, re.S))
text = html.unescape(re.sub(r"<[^>]+>", "", page))
anchor = re.compile(r"`([\w./@+-]+):(\d+)(?:-(\d+))?`(?:-`(\d+)`)?")
md_anchors = {m.group(1) + ":" + m.group(2) + ("-" + (m.group(3) or m.group(4)) if (m.group(3) or m.group(4)) else "")
              for m in anchor.finditer(md) if "." in m.group(1) or "/" in m.group(1)}
heads = {re.sub(r"[`*]", "", h).strip() for h in re.findall(r"^#{2,3} (.+)$", md, re.M)}

bad = []
if md_diagrams != html_diagrams:
    bad.append(f"diagrams differ: markdown {len(md_diagrams)}, html {len(html_diagrams)}")
bad += [f"anchor missing in html: {a}" for a in sorted(md_anchors) if a not in text]
bad += [f"heading missing in html: {h}" for h in sorted(heads) if h not in text]
if not re.search(r'<script src="https://cdn\.jsdelivr\.net/npm/mermaid@\d+\.\d+\.\d+/', page):
    bad.append("mermaid script is not pinned to an exact jsdelivr version")
if "diagram-note" not in page or 'id="mermaid-banner"' not in page:
    bad.append("fallback notice missing")
if re.search(r'(?:src|href)="(?!https://cdn\.jsdelivr\.net/|#)[a-z]+://', page):
    bad.append("page loads something besides the pinned Mermaid script")
print("\n".join(bad) or f"html ok: {len(html_diagrams)} diagrams, {len(md_anchors)} anchors")
sys.exit(1 if bad else 0)
```

A failure is repaired in the Markdown first when the Markdown is wrong, then
the page is regenerated from it.

## Opening it

Print one of these in the handoff, with the real absolute path:

- `lavish-axi` on `PATH` (check with `command -v lavish-axi`; never run it
  yourself): `lavish-axi <path of the page>` (`<ROOT>/.onboarding/index.html`,
  `<ROOT>/.pr-review/pr-<n>/brief.html`), which opens it in Lavish with
  annotation and feedback.
- Otherwise open the file in a browser (`open` on macOS, `xdg-open` on Linux,
  `start` on Windows), or from the IDE: right-click the file, Open in Browser.

The page needs network only for the Mermaid script. Offline, or when
`cdn.jsdelivr.net` is blocked, the guide still reads in full and each diagram
shows its source; the Markdown preview in the IDE renders them natively.
