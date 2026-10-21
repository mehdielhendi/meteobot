from pathlib import Path

html_path = Path("app/static/index.html")
html = html_path.read_text(encoding="utf-8")
frag = Path("data/vigilance_map_fragment.html").read_text(encoding="utf-8")
start = html.index('        <div class="vigilance__board"')
end = html.index("      </section>", start)
html_path.write_text(html[:start] + frag + html[end:], encoding="utf-8")
print("patched", start, "->", end)
