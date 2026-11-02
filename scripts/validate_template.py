#!/usr/bin/env python3
"""Static checks for this template's Claude Code configuration. Stdlib only.

Checks structure and text, not model behavior: passing means the configuration is
consistent, not that Claude will follow it.

Usage: python scripts/validate_template.py [repo_root]
Exit 0 = all checks pass, 1 = errors (listed on stderr).
"""
from __future__ import annotations  # `X | None` annotations on Python 3.9

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
READ_ONLY_AGENTS = re.compile(r"(reviewer|auditor|analyst)")
AGENT_LIKE = re.compile(r"^[a-z]+(-[a-z]+)*-(architect|builder|reviewer|auditor|debugger|engineer|analyst|lite)$"
                        r"|^(architect|builder|reviewer|debugger)$")
BUILTIN_COMMANDS = {"compact", "context", "clear", "help", "config", "model", "agents", "init",
                    "memory", "permissions", "hooks", "review", "code-review", "security-review"}
# Historical docs may name agents that no longer exist.
REFERENCE_EXEMPT = {"docs/audit-v2.md"}
REQUIRED_DENY = ["Bash(git add -A)", "Bash(git add .)", "Bash(git add --all)",
                 "Bash(git push --force *)", "Read(**/.env)", "Read(**/.env.*)",
                 "Edit(**/.env)", "Edit(**/.env.*)"]
# Each hook script and the tools its matcher must cover.
REQUIRED_HOOKS = {"guard-bash.sh": {"Bash"},
                  "guard-files.sh": {"Read", "Edit", "Write", "MultiEdit", "NotebookEdit", "Grep"}}
GATES = ("test", "lint", "typecheck", "build")
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
    covered: dict[str, set[str]] = {}
    for entry in settings.get("hooks", {}).get("PreToolUse", []):
        tools = {t.strip() for t in re.split(r"[|,]", entry.get("matcher", ""))}
        for h in entry.get("hooks", []):
            for script in re.findall(r"\.claude/hooks/([\w.-]+\.sh)", h.get("command", "")):
                covered.setdefault(script, set()).update(tools)
                if not (ROOT / ".claude/hooks" / script).exists():
                    err(path, f"hook runs missing .claude/hooks/{script}")
                if h.get("onFailure") != "block":
                    err(path, f"hook {script} must set \"onFailure\": \"block\" (fail closed)")
    for script, tools in REQUIRED_HOOKS.items():
        missing = tools - covered.get(script, set())
        if missing:
            err(path, f"PreToolUse hook {script} must cover {', '.join(sorted(missing))}")
    if not (ROOT / ".claude/hooks/scan-secrets.sh").exists():
        err(path, "missing .claude/hooks/scan-secrets.sh")
    check_profiles(settings)


def profile_state() -> dict | None:
    path = ROOT / ".claude/profile-state.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        err(path, f"invalid JSON: {e}")
        return None


def check_profiles(settings: dict) -> None:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import configure  # noqa: E402  (stdlib-only sibling module)
    folder = ROOT / ".claude/profiles"
    found = {}
    for p in sorted(folder.glob("*.json")):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            err(p, f"invalid JSON: {e}")
            continue
        if not data.get("description") or not isinstance(data.get("settings"), dict):
            err(p, "profile needs 'description' and a 'settings' object")
            continue
        if data["settings"].get("env", {}).get("CLAUDE_TEMPLATE_PROFILE") != p.stem:
            err(p, f"settings.env.CLAUDE_TEMPLATE_PROFILE must be '{p.stem}'")
        found[p.stem] = data
    for name in ("solo", "team", "high-security"):
        if name not in found:
            err(".claude/profiles", f"missing profile '{name}'")
    current = settings.get("env", {}).get("CLAUDE_TEMPLATE_PROFILE")
    if current not in found:
        err(".claude/settings.json", f"env.CLAUDE_TEMPLATE_PROFILE '{current}' is not a profile in .claude/profiles/")
    elif configure.apply_profile(settings, current, found, profile_state())[0] != settings:
        err(".claude/settings.json", f"out of sync with profile '{current}': run python scripts/configure.py profile {current}")


def check_quality_gates() -> None:
    conf = ROOT / ".claude/quality-gates.conf"
    if not (ROOT / "scripts/quality-gates.sh").exists():
        err("scripts/quality-gates.sh", "missing")
    if not conf.exists():
        err(".claude/quality-gates.conf", "missing")
        return
    keys = {m.group(1) for m in re.finditer(r"^\s*(\w+)\s*=", conf.read_text(encoding="utf-8"), re.M)}
    for gate in GATES:
        if gate not in keys:
            err(conf, f"missing '{gate}=' line (use '{gate}=none' if not applicable)")
    ci = ROOT / ".github/workflows/checks.yml"
    if ci.exists():
        text = ci.read_text(encoding="utf-8")
        for needle, what in (("scripts/quality-gates.sh", "run the quality gates"), ("gitleaks", "run gitleaks")):
            if needle not in text:
                err(ci, f"CI must {what}")


def check_workflow_rules() -> None:
    claude = ROOT / "CLAUDE.md"
    text = claude.read_text(encoding="utf-8")
    if len(text.splitlines()) > MAX_CLAUDE_MD_LINES:
        err(claude, f"over {MAX_CLAUDE_MD_LINES} lines")
    required = {
        "## Security baseline": "security baseline section",
        "**Security override:**": "security override (small security change → Deep)",
        "completed | blocked | needs_escalation": "result contract statuses",
        "## Quality gates": "quality gates section",
    }
    for needle, what in required.items():
        if needle not in text:
            err(claude, f"missing {what}")
    workflow = ROOT / ".claude/skills/workflow/SKILL.md"
    if not workflow.exists():
        err(workflow, "missing (holds the per-mode steps and loop rules)")
    elif "Max **2**" not in workflow.read_text(encoding="utf-8"):
        err(workflow, "missing 2-cycle cap on review loops")
    # Mode table: header "| Signal | Trivial | Fast | Normal | Deep |", row "| Workflow | ... |".
    cells = lambda line: [c.strip() for c in line.strip().strip("|").split("|")]
    header = re.search(r"^\| Signal \|.*$", text, re.M)
    row = re.search(r"^\| Workflow \|.*$", text, re.M)
    workflow = dict(zip(cells(header.group(0))[1:], cells(row.group(0))[1:])) if header and row else {}
    for mode in ("Trivial", "Fast"):
        cell = workflow.get(mode, "")
        if "No subagents" not in cell or re.search(r"`[a-z-]+`", cell):
            err(claude, f"{mode} workflow must run without subagents")
    if "`architect`" in workflow.get("Normal", "") or "`reviewer`" in workflow.get("Normal", ""):
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
    check_quality_gates()
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
