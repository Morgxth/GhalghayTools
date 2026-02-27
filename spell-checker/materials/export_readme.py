"""
Конвертирует README.md в красивый самодостаточный HTML-файл.
Запуск: python materials/export_readme.py
Результат: README.html в корне проекта.
"""

import markdown
import pathlib
import re

ROOT = pathlib.Path(__file__).parent.parent
src = (ROOT / "README.md").read_text(encoding="utf-8")

# Рендер: таблицы + переносы строк как в GitHub
md = markdown.Markdown(extensions=["tables", "fenced_code", "nl2br"])
body = md.convert(src)

CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }

body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
  font-size: 16px;
  line-height: 1.7;
  color: #24292f;
  background: #ffffff;
  padding: 3rem 1rem;
}

.container {
  max-width: 860px;
  margin: 0 auto;
}

h1, h2, h3, h4 {
  line-height: 1.3;
  font-weight: 600;
  margin-top: 1.8rem;
  margin-bottom: 0.6rem;
  border-bottom: 1px solid #eaecef;
  padding-bottom: 0.3rem;
}
h1 { font-size: 2rem; border-bottom-width: 2px; }
h2 { font-size: 1.5rem; }
h3 { font-size: 1.2rem; border-bottom: none; }

p { margin: 0.7rem 0; }

a { color: #0969da; text-decoration: none; }
a:hover { text-decoration: underline; }

code {
  background: #f6f8fa;
  border: 1px solid #e1e4e8;
  border-radius: 4px;
  padding: 0.15em 0.4em;
  font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace;
  font-size: 0.88em;
}

pre {
  background: #f6f8fa;
  border: 1px solid #e1e4e8;
  border-radius: 8px;
  padding: 1.1rem 1.3rem;
  overflow-x: auto;
  margin: 1rem 0;
}
pre code {
  background: none;
  border: none;
  padding: 0;
  font-size: 0.9em;
  line-height: 1.55;
}

table {
  width: 100%;
  border-collapse: collapse;
  margin: 1rem 0;
  font-size: 0.95rem;
}
th, td {
  border: 1px solid #d0d7de;
  padding: 0.5rem 0.85rem;
  text-align: left;
}
th {
  background: #f6f8fa;
  font-weight: 600;
}
tr:nth-child(even) { background: #f6f8fa; }

ul, ol {
  padding-left: 1.8rem;
  margin: 0.6rem 0;
}
li { margin: 0.25rem 0; }

li input[type=checkbox] {
  margin-right: 0.4rem;
}

blockquote {
  border-left: 4px solid #d0d7de;
  padding: 0.4rem 1rem;
  color: #57606a;
  margin: 0.8rem 0;
}

hr {
  border: none;
  border-top: 2px solid #eaecef;
  margin: 2rem 0;
}
"""

html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>ГIалгIай мотт — Проверка орфографии</title>
  <style>{CSS}</style>
</head>
<body>
  <div class="container">
    {body}
  </div>
</body>
</html>"""

# GitHub-style checkboxes: [ ] и [x]
html = re.sub(r"\[ \]", '<input type="checkbox" disabled>', html)
html = re.sub(r"\[x\]", '<input type="checkbox" checked disabled>', html)

out = ROOT / "README.html"
out.write_text(html, encoding="utf-8")
print(f"OK: {out}")
