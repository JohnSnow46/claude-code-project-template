#!/usr/bin/env python3
"""Static checks for this template's Claude Code configuration. Stdlib only.

Checks structure and text, not model behavior: passing means the configuration is
consistent, not that Claude will follow it.

Usage: python scripts/validate_template.py [repo_root]
Exit 0 = all checks pass, 1 = errors (listed on stderr).
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent)

MODELS = {"sonnet", "opus", "haiku", "fable", "inherit"}
MAX_DESCRIPTION_CHARS = 450      # descriptions load into every session
MAX_SKILL_WORDS = 600            # skill bodies load whole when used
MAX_AGENT_WORDS = 600
MAX_CLAUDE_MD_LINES = 130        # loads into every conversation
READ_ONLY_AGENTS = re.compile(r"(reviewer|auditor)")
AGENT_LIKE = re.compile(r"^[a-z]+(-[a-z]+)*-(architect|builder|reviewer|auditor|debugger|engineer|lite)$"
                        r"|^(architect|builder|reviewer|debugger)$")
BUILTIN_COMMANDS = {"compact", "context", "clear", "help", "config", "model", "agents", "init",
                    "memory", "permissions", "hooks", "review", "code-review", "security-review"}
# Historical docs may name agents that no longer exist.
REFERENCE_EXEMPT = {"docs/audit-v2.md"}
REQUIRED_DENY = ["Bash(git add -A)", "Bash(git add .)", "Bash(git add --all)",
                 "Bash(git push --force *)", "Read(./.env)"]
FORBIDDEN_ALLOW = re.compile(r"^Bash(\(\*\))?$|^Bash\((git push|git add|rm |sudo|curl|wget)")

errors: list[str] = []


def err(path: Path | str, msg: str) -> None:
    errors.append(f"{Path(path).relative_to(ROOT) if isinstance(path, Path) else path}: {msg}")


def frontmatter(path: Path) -> tuple[dict, str]:
    text = path.read_text(encoding="utf-8")
    m = re.match(r"^---\r?\n(.*?)\r?\n---\r?\n(.*)$", text, re.S)
    if not m:
        err(path, "missing YAML frontmatter")
        return {}, text
    fields = {}
    for line in m.group(1).splitlines():
        if not line.strip() or line.startswith((" ", "#")):
            continue
        key, sep, value = line.partition(":")
        if not sep:
            err(path, f"malformed frontmatter line: {line!r}")
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        fields[key.strip()] = value
    return fields, m.group(2)


def words(text: str) -> int:
    return len(re.sub(r"```.*?```", "", text, flags=re.S).split())


def check_agents() -> set[str]:
    names = set()
    for path in sorted((ROOT / ".claude/agents").glob("*.md")):
        fm, body = frontmatter(path)
        name = fm.get("name", "")
        names.add(name)
        if name != path.stem:
            err(path, f"name '{name}' doesn't match file name '{path.stem}'")
        for key in ("description", "tools", "model"):
            if not fm.get(key):
                err(path, f"missing '{key}'")
        if fm.get("model") and fm["model"] not in MODELS and not fm["model"].startswith("claude-"):
            err(path, f"unknown model '{fm['model']}'")
        if len(fm.get("description", "")) > MAX_DESCRIPTION_CHARS:
            err(path, f"description over {MAX_DESCRIPTION_CHARS} chars")
        tools = {t.strip() for t in fm.get("tools", "").split(",")}
        if READ_ONLY_AGENTS.search(name) and tools & {"Write", "Edit", "NotebookEdit"}:
            err(path, "review/audit agents must be read-only (no Write/Edit)")
        if "result block" not in body:
            err(path, "doesn't end with the result block from CLAUDE.md")
        if words(body) > MAX_AGENT_WORDS:
            err(path, f"body over {MAX_AGENT_WORDS} words")
    return names


def check_skills() -> set[str]:
    names = set()
    for path in sorted((ROOT / ".claude/skills").glob("*/SKILL.md")):
        fm, body = frontmatter(path)
        name = fm.get("name", "")
        names.add(name)
        if name != path.parent.name:
            err(path, f"name '{name}' doesn't match directory '{path.parent.name}'")
        if not fm.get("description"):
            err(path, "missing 'description'")
        if len(fm.get("description", "")) > MAX_DESCRIPTION_CHARS:
            err(path, f"description over {MAX_DESCRIPTION_CHARS} chars")
        if fm.get("disable-model-invocation") not in (None, "true", "false"):
            err(path, "disable-model-invocation must be true or false")
        if words(body) > MAX_SKILL_WORDS:
            err(path, f"body over {MAX_SKILL_WORDS} words")
    return names


def markdown_files() -> list[Path]:
    return [p for p in ROOT.rglob("*.md")
            if not any(part.startswith(".git") or part == "node_modules" for part in p.relative_to(ROOT).parts)]


def check_references(agents: set[str], skills: set[str]) -> None:
    for path in markdown_files():
        rel = path.relative_to(ROOT).as_posix()
        text = path.read_text(encoding="utf-8")
        prose = re.sub(r"```.*?```", "", text, flags=re.S)
        for target in re.findall(r"\]\(([^)\s]+)\)", prose):
            if re.match(r"^(https?:|mailto:|#)", target):
                continue
            file_part = target.split("#", 1)[0]
            if file_part and not (path.parent / file_part).exists():
                err(path, f"broken link '{target}'")
        if rel in REFERENCE_EXEMPT:
            continue
        for token in re.findall(r"`([^`\n]+)`", prose):
            if AGENT_LIKE.match(token) and token not in agents:
                err(path, f"references unknown agent `{token}`")
            m = re.match(r"^/([a-z][a-z-]*)(\s|$)", token)
            if m and m.group(1) not in skills | BUILTIN_COMMANDS:
                err(path, f"references unknown command `{token}`")
        for ref in re.findall(r"\.claude/(agents|skills)/([a-z][a-z0-9-]*)", text):
            kind, name = ref
            if (kind == "agents" and name not in agents) or (kind == "skills" and name not in skills):
                err(path, f"references missing .claude/{kind}/{name}")


def check_settings() -> None:
    path = ROOT / ".claude/settings.json"
    try:
        settings = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        err(path, f"invalid JSON: {e}")
        return
    perms = settings.get("permissions", {})
    for rule in REQUIRED_DENY:
        if rule not in perms.get("deny", []):
            err(path, f"permissions.deny missing {rule}")
    for rule in perms.get("allow", []):
        if FORBIDDEN_ALLOW.search(rule):
            err(path, f"permissions.allow must not pre-approve {rule}")
    if not any("git push" in r for r in perms.get("ask", []) + perms.get("deny", [])):
        err(path, "git push must be in permissions.ask (or deny)")
    commands = [h.get("command", "")
                for entry in settings.get("hooks", {}).get("PreToolUse", [])
                if entry.get("matcher") == "Bash"
                for h in entry.get("hooks", [])]
    if not any("guard-bash.sh" in c for c in commands):
        err(path, "PreToolUse Bash hook must run .claude/hooks/guard-bash.sh")
    for script in ("guard-bash.sh", "scan-secrets.sh"):
        if not (ROOT / ".claude/hooks" / script).exists():
            err(path, f"missing .claude/hooks/{script}")


def check_workflow_rules() -> None:
    claude = ROOT / "CLAUDE.md"
    text = claude.read_text(encoding="utf-8")
    if len(text.splitlines()) > MAX_CLAUDE_MD_LINES:
        err(claude, f"over {MAX_CLAUDE_MD_LINES} lines")
    required = {
        "## Security baseline": "security baseline section",
        "**Security override:**": "security override (small security change → Deep)",
        "completed | blocked | needs_escalation": "result contract statuses",
        "Max **2**": "2-cycle cap on review loops",
    }
    for needle, what in required.items():
        if needle not in text:
            err(claude, f"missing {what}")
    fast = re.search(r"^\| \*\*Fast\*\* \|(.*)$", text, re.M)
    if not fast or "No subagents" not in fast.group(1) or re.search(r"`[a-z-]+`", fast.group(1)):
        err(claude, "Fast workflow must run without subagents")
    normal = re.search(r"^\| \*\*Normal\*\* \|(.*)$", text, re.M)
    if normal and ("`architect`" in normal.group(1) or "`reviewer`" in normal.group(1)):
        err(claude, "Normal workflow must not use full architect/reviewer")
    feature = ROOT / ".claude/skills/feature/SKILL.md"
    if feature.exists():
        ftext = feature.read_text(encoding="utf-8")
        for needle in ("Max 2 cycles", "needs_escalation", "blocked"):
            if needle not in ftext:
                err(feature, f"missing '{needle}'")


def main() -> int:
    agents = check_agents()
    skills = check_skills()
    check_references(agents, skills)
    check_settings()
    check_workflow_rules()
    if errors:
        print(f"{len(errors)} problem(s):", file=sys.stderr)
        for e in errors:
            print(f"  {e}", file=sys.stderr)
        return 1
    print(f"OK: {len(agents)} agents, {len(skills)} skills, {len(markdown_files())} markdown files checked.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
