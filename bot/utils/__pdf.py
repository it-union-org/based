"""
    Desc: converts note.md to PDF and sends it via MAX Bot API
    Creator: Kirosha
"""

from __future__ import annotations

import re
from pathlib import Path

import aiohttp

from based.utils.__console import log_err, log_ok, log_warn


API_BASE = "https://platform-api2.max.ru"


CSS = """
@page { size: A4; margin: 20mm 18mm; }
body {
    font-family: "DejaVu Sans", "Segoe UI", Arial, sans-serif;
    font-size: 11pt;
    line-height: 1.55;
    color: #1f2328;
}
h1 { font-size: 20pt; border-bottom: 2px solid #1f2328; padding-bottom: 6px; margin-top: 0; }
h2 { font-size: 15pt; border-bottom: 1px solid #d0d7de; padding-bottom: 4px; margin-top: 22px; }
h3 { font-size: 13pt; margin-top: 16px; }
code {
    font-family: "JetBrains Mono", "Consolas", monospace;
    font-size: 9.5pt;
    background: #f6f8fa;
    padding: 1px 4px;
    border-radius: 3px;
}
pre {
    background: #f6f8fa;
    padding: 10px 12px;
    border-radius: 6px;
    white-space: pre-wrap;
    word-wrap: break-word;
}
pre code { background: none; padding: 0; }
table { border-collapse: collapse; width: 100%; margin: 12px 0; }
th, td { border: 1px solid #d0d7de; padding: 6px 10px; text-align: left; }
th { background: #f6f8fa; }
blockquote {
    border-left: 4px solid #d0d7de;
    margin: 12px 0;
    padding: 2px 14px;
    color: #57606a;
}
ul, ol { padding-left: 22px; }
img { max-width: 100%; }
.mermaid { text-align: center; margin: 16px 0; }
mjx-container { font-size: 105% !important; }
"""


MERMAID_BLOCK = re.compile(r"```mermaid\s*\n(.*?)```", re.DOTALL)
DIAGRAM_HEADER = re.compile(
    r"^(graph|flowchart|sequenceDiagram|classDiagram|stateDiagram|"
    r"stateDiagram-v2|erDiagram|gantt|pie|journey|mindmap|timeline)\b"
)
# узел вида X[...] или X(...) или X{...}, где X — идентификатор перед скобкой
NODE_SQUARE = re.compile(r"([A-Za-z0-9_]+)\[([^\[\]]*)\]")
NODE_ROUND = re.compile(r"([A-Za-z0-9_]+)\(([^()]*)\)")
NODE_CURLY = re.compile(r"([A-Za-z0-9_]+)\{([^{}]*)\}")


def _needs_quote(text: str) -> bool:
    """Нужны ли кавычки вокруг текста узла."""
    if not text:
        return False
    if text.startswith('"') and text.endswith('"'):
        return False
    return bool(re.search(r"[()\[\]{}&;<>|\\]", text))


def _quote(text: str) -> str:
    cleaned = text.strip().replace('"', "'")
    return '["' + cleaned + '"]'


def _fix_line(line: str) -> str:
    stripped = line.rstrip()
    if not stripped or stripped.lstrip().startswith("%%"):
        return line

    def fix_square(m: re.Match) -> str:
        ident, inner = m.group(1), m.group(2)
        if _needs_quote(inner):
            return f'{ident}{_quote(inner)}'
        return m.group(0)

    def fix_round(m: re.Match) -> str:
        ident, inner = m.group(1), m.group(2)
        if _needs_quote(inner):
            return f'{ident}{_quote(inner)}'
        return m.group(0)

    def fix_curly(m: re.Match) -> str:
        ident, inner = m.group(1), m.group(2)
        if _needs_quote(inner):
            return f'{ident}{_quote(inner)}'
        return m.group(0)

    result = stripped
    result = NODE_SQUARE.sub(fix_square, result)
    result = NODE_ROUND.sub(fix_round, result)
    result = NODE_CURLY.sub(fix_curly, result)
    return result


def sanitize_mermaid(text: str) -> str:
    """Чинит типичные ошибки LLM в mermaid-блоках, не залезая в формулы."""

    def fix_block(match: re.Match) -> str:
        body = match.group(1).strip()
        lines = [ln for ln in body.splitlines()]
        if not lines:
            return match.group(0)

        first = lines[0].strip()
        if DIAGRAM_HEADER.match(first):
            header = first
            rest = lines[1:]
        else:
            header = "graph TD"
            rest = lines

        fixed = [header] + [_fix_line(ln) for ln in rest]
        return "```mermaid\n" + "\n".join(fixed).rstrip() + "\n```"

    return MERMAID_BLOCK.sub(fix_block, text)


def md_to_pdf(md_path: Path, pdf_path: Path) -> bool:
    """Синхронно конвертирует Markdown с LaTeX и Mermaid в PDF."""
    try:
        import markdown
        from playwright.sync_api import sync_playwright
    except ImportError as err:
        log_err(f"нужны пакеты: pip install markdown playwright && playwright install chromium ({err})")
        return False

    body = md_path.read_text(encoding="utf-8")
    body = sanitize_mermaid(body)

    html_body = markdown.markdown(
        body,
        extensions=["extra", "tables", "fenced_code", "sane_lists", "md_in_html"],
    )

    html_doc = f"""<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<title>{md_path.stem}</title>
<script>
window.MathJax = {{
    tex: {{
        inlineMath: [['$', '$'], ['\\\\(', '\\\\)']],
        displayMath: [['$$', '$$'], ['\\\\[', '\\\\]']],
        processEscapes: true,
    }},
    svg: {{ fontCache: 'global' }},
    options: {{
        skipHtmlTags: ['script', 'noscript', 'style', 'textarea', 'pre', 'code'],
    }},
}};
</script>
<script src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-svg.js"></script>
<script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
<script>
document.addEventListener("DOMContentLoaded", function () {{
    mermaid.initialize({{ startOnLoad: false, theme: "default", securityLevel: "loose" }});
    document.querySelectorAll("pre > code").forEach(function (el) {{
        const text = el.textContent.trim();
        if (/^(graph|flowchart|sequenceDiagram|classDiagram|stateDiagram|erDiagram|gantt|pie|journey|mindmap|timeline)/.test(text)) {{
            const container = document.createElement("div");
            container.className = "mermaid";
            container.textContent = text;
            el.parentElement.replaceWith(container);
        }}
    }});
    mermaid.run({{ querySelector: ".mermaid" }}).catch(function (err) {{
        console.error("mermaid error:", err);
    }});
}});
</script>
<style>{CSS}</style>
</head>
<body>
{html_body}
</body>
</html>"""

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()

            def on_console(msg):
                if msg.type == "error":
                    log_err(f"pdf page: {msg.text}")

            page.on("console", on_console)
            page.set_content(html_doc, wait_until="networkidle")
            page.wait_for_timeout(4000)
            page.pdf(
                path=str(pdf_path),
                format="A4",
                margin={"top": "20mm", "bottom": "20mm", "left": "18mm", "right": "18mm"},
                print_background=True,
            )
            browser.close()
    except Exception as err:
        log_err(f"playwright: {err.__class__.__name__}: {err}")
        return False

    return pdf_path.exists() and pdf_path.stat().st_size > 0


async def upload_file(token: str, file_path: Path, file_type: str = "file") -> str | None:
    headers = {"Authorization": token}
    connector = aiohttp.TCPConnector(ssl=False)

    async with aiohttp.ClientSession(headers=headers, connector=connector) as session:
        async with session.post(f"{API_BASE}/uploads?type={file_type}") as resp:
            if resp.status != 200:
                log_err(f"uploads error: {resp.status} {await resp.text()}")
                return None
            data = await resp.json()
            upload_url = data.get("url")
            if not upload_url:
                log_err(f"no url in response: {data}")
                return None

        form = aiohttp.FormData()
        form.add_field(
            "data",
            file_path.read_bytes(),
            filename=file_path.name,
            content_type="application/pdf",
        )
        async with session.post(upload_url, data=form) as resp:
            if resp.status != 200:
                log_err(f"upload error: {resp.status} {await resp.text()}")
                return None
            result = await resp.json()

        file_token = (
            result.get("token")
            or (result.get("photos") or {}).get("token")
            or result.get("file_token")
        )
        if not file_token:
            log_err(f"no token in upload response: {result}")
            return None
        return file_token


async def send_file(
    token: str,
    user_id: str,
    file_token: str,
    caption: str = "",
    max_attempts: int = 10,
    delay_seconds: float = 1.5,
) -> bool:
    """Отправляет сообщение с файлом, повторяя попытку при attachment.not.ready."""
    import asyncio

    headers = {"Authorization": token, "Content-Type": "application/json"}
    payload = {
        "text": caption,
        "attachments": [{"type": "file", "payload": {"token": file_token}}],
    }
    connector = aiohttp.TCPConnector(ssl=False)
    async with aiohttp.ClientSession(headers=headers, connector=connector) as session:
        for attempt in range(1, max_attempts + 1):
            async with session.post(
                f"{API_BASE}/messages?user_id={user_id}",
                json=payload,
            ) as resp:
                body = await resp.text()
                if resp.status == 200:
                    log_ok(f"sent pdf: {resp.status}")
                    return True
                if "attachment.not.ready" in body or "not.processed" in body:
                    log_warn(
                        f"send pdf attempt {attempt}/{max_attempts}: "
                        f"attachment not ready, retrying in {delay_seconds}s"
                    )
                    await asyncio.sleep(delay_seconds)
                    continue
                log_err(f"send error: {resp.status} {body}")
                return False
    log_err(f"send pdf failed after {max_attempts} attempts")
    return False
