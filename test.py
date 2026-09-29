"""
    Desc: checks the repository before submission
    Creator: Kirosha

    Запуск:
        python check_repo.py
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

OK = "[ok]  "
FAIL = "[fail]"
WARN = "[warn]"
INFO = "[info]"

REQUIRED = [
    "README.md",
    "Dockerfile",
    "compose.yaml",
    ".dockerignore",
    ".env.example",
    ".gitignore",
    "pyproject.toml",
    "requirements.txt",
    "requirements-bot.txt",
    "requirements-skeds.txt",
    "verify.py",
    "LICENSE",
    "based/README.md",
    "bot/README.md",
    "samples/README.md",
]

JUNK_PATTERNS = [
    "product.py",
    "main.py",
    "make_*.py",
    "patch_*.py",
    "step*.py",
    "fix_*.py",
    "send_note.py",
    "_fetch_readmes.py",
    "dump_project.py",
]

SECRET_PATTERNS = [
    re.compile(r"BOT_TOKEN\s*=\s*[A-Za-z0-9_\-\.]{20,}"),
    re.compile(r"(?i)(api[_-]?key|secret|password|bearer)\s*[:=]\s*['\"]?[A-Za-z0-9_\-\.]{20,}"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"ghp_[A-Za-z0-9]{36,}"),
]

SCAN_EXTENSIONS = {
    ".py", ".md", ".txt", ".yaml", ".yml", ".toml", ".json",
    ".cfg", ".ini", ".env", ".example", ".sh", ".ps1",
}

SKIP_DIRS = {
    ".venv", "venv", ".git", ".idea", ".vscode",
    "__pycache__", ".pytest_cache", ".ruff_cache",
    ".mypy_cache", "node_modules", "dist", "build",
    ".egg-info", "samples/output",
}


def run_git(args: list[str]) -> tuple[int, str]:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
        )
        return result.returncode, (result.stdout or "") + (result.stderr or "")
    except FileNotFoundError:
        return 1, "git not found"


def section(title: str) -> None:
    print()
    print("=" * 60)
    print(f"  {title}")
    print("=" * 60)


def check_git_repo() -> bool:
    code, _ = run_git(["rev-parse", "--is-inside-work-tree"])
    return code == 0


def check_commit_hash() -> tuple[bool, str]:
    code, out = run_git(["rev-parse", "HEAD"])
    if code != 0:
        return False, "нет коммитов"
    return True, out.strip()


def check_env_not_tracked() -> bool:
    code, out = run_git(["ls-files"])
    if code != 0:
        return False
    tracked = [line.strip() for line in out.splitlines() if line.strip()]
    bad = [f for f in tracked if f == ".env" or f.endswith("/.env")]
    return len(bad) == 0


def check_gitignore() -> bool:
    path = ROOT / ".gitignore"
    if not path.exists():
        return False
    text = path.read_text(encoding="utf-8")
    need = [".env", "__pycache__", ".venv"]
    return all(n in text for n in need)


def check_required_files() -> list[str]:
    missing = []
    for rel in REQUIRED:
        if not (ROOT / rel).exists():
            missing.append(rel)
    return missing


def check_env_example_clean() -> list[str]:
    path = ROOT / ".env.example"
    if not path.exists():
        return [".env.example не найден"]
    issues = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("BOT_TOKEN="):
            value = line.split("=", 1)[1].strip()
            if value:
                issues.append(f"BOT_TOKEN в .env.example не пустой: {value[:20]}...")
    return issues


def iter_files() -> list[Path]:
    result = []
    for p in ROOT.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(ROOT)
        parts = set(rel.parts)
        if parts & SKIP_DIRS:
            continue
        if p.suffix.lower() not in SCAN_EXTENSIONS and p.name not in {
            "Dockerfile", "Makefile", ".env", ".env.example", ".gitignore", ".dockerignore"
        }:
            continue
        result.append(p)
    return result


def scan_secrets() -> list[tuple[str, str]]:
    hits = []
    for path in iter_files():
        rel = path.relative_to(ROOT).as_posix()
        if rel == "check_repo.py":
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for pattern in SECRET_PATTERNS:
            for m in pattern.finditer(text):
                snippet = m.group(0)[:60]
                hits.append((rel, snippet))
    return hits


def find_junk() -> list[str]:
    found = []
    for pattern in JUNK_PATTERNS:
        for p in ROOT.glob(pattern):
            if p.is_file() and p.name != "check_repo.py":
                found.append(p.name)
    return sorted(set(found))


def check_docs_image() -> bool:
    path = ROOT / "docs" / "main_menu.png"
    return path.exists()


def check_readme_mentions() -> list[str]:
    path = ROOT / "README.md"
    if not path.exists():
        return ["README.md не найден"]
    text = path.read_text(encoding="utf-8")
    issues = []
    if "[based/README.md]" not in text and "based/README.md" not in text:
        issues.append("нет ссылки на based/README.md")
    if "docker compose up" not in text:
        issues.append("нет команды docker compose up")
    if "verify.py" not in text:
        issues.append("нет упоминания verify.py")
    return issues


def main() -> int:
    problems = 0
    warnings = 0

    section("git")
    if check_git_repo():
        print(f"{OK} это git-репозиторий")
    else:
        print(f"{FAIL} не git-репозиторий. Запусти: git init && git add . && git commit")
        problems += 1

    ok, info = check_commit_hash()
    if ok:
        print(f"{OK} commit hash: {info}")
    else:
        print(f"{FAIL} {info}")
        problems += 1

    if check_env_not_tracked():
        print(f"{OK} .env не отслеживается git")
    else:
        print(f"{FAIL} .env попал в git! Срочно: git rm --cached .env")
        problems += 1

    if check_gitignore():
        print(f"{OK} .gitignore содержит нужные правила")
    else:
        print(f"{FAIL} .gitignore неполный")
        problems += 1

    section("обязательные файлы")
    missing = check_required_files()
    if not missing:
        print(f"{OK} все {len(REQUIRED)} файлов на месте")
    else:
        for m in missing:
            print(f"{FAIL} нет {m}")
        problems += len(missing)

    section("секреты")
    env_issues = check_env_example_clean()
    if env_issues:
        for issue in env_issues:
            print(f"{FAIL} {issue}")
        problems += len(env_issues)
    else:
        print(f"{OK} .env.example чистый")

    secret_hits = scan_secrets()
    if secret_hits:
        for rel, snippet in secret_hits:
            print(f"{WARN} {rel}: {snippet}")
        warnings += len(secret_hits)
    else:
        print(f"{OK} секретов в файлах не найдено")

    section("мусор в корне")
    junk = find_junk()
    if junk:
        for name in junk:
            print(f"{WARN} {name}")
        warnings += len(junk)
        print("  → эти файлы можно убрать в tools/ или удалить")
    else:
        print(f"{OK} лишних файлов нет")

    section("документация")
    if check_docs_image():
        print(f"{OK} docs/main_menu.png существует")
    else:
        print(f"{WARN} docs/main_menu.png отсутствует, но README на него ссылается")
        warnings += 1

    readme_issues = check_readme_mentions()
    if readme_issues:
        for issue in readme_issues:
            print(f"{WARN} {issue}")
        warnings += len(readme_issues)
    else:
        print(f"{OK} README содержит ключевые разделы")

    section("итог")
    print(f"проблем: {problems}")
    print(f"предупреждений: {warnings}")
    if problems == 0 and warnings == 0:
        print(f"\n{OK} репозиторий готов к сдаче")
        return 0
    if problems == 0:
        print(f"\n{OK} критичных проблем нет, но есть предупреждения")
        return 0
    print(f"\n{FAIL} есть критичные проблемы, исправь перед сдачей")
    return 1


if __name__ == "__main__":
    sys.exit(main())