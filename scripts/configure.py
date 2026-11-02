#!/usr/bin/env python3
"""Configure this template: security profile and agent models. Stdlib only.

  python scripts/configure.py show
  python scripts/configure.py profile <solo|team|high-security>
  python scripts/configure.py models [--strong M] [--standard M] [--all M] [--fallback M1,M2]

Profiles (.claude/profiles/<name>.json) are overlays on .claude/settings.json.
.claude/profile-state.json records exactly what the active profile changed (rules it
added, values it replaced); switching undoes only that, then applies the new overlay.
A rule you had before a profile was applied is never recorded, so it's never removed.

Models: agents are split into two tiers. `strong` does design/review/audit, `standard`
does everything else. Use aliases (opus, sonnet, haiku), a full model ID, or `inherit`
(use whatever model the main session runs — never fails on model access). `--fallback`
writes `fallbackModel` in settings.json: the chain Claude Code tries when the primary
model is overloaded or unavailable.
"""
from __future__ import annotations  # `X | None` annotations on Python 3.9 (stock macOS)

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STRONG_AGENTS = {"architect", "reviewer", "security-auditor"}
MODEL_RE = re.compile(r"^(sonnet|opus|haiku|fable|inherit|claude-[a-z0-9.-]+)$")


def settings_path(root: Path) -> Path:
    return root / ".claude" / "settings.json"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


def profiles(root: Path) -> dict[str, dict]:
    return {p.stem: load_json(p) for p in sorted((root / ".claude" / "profiles").glob("*.json"))}


def state_path(root: Path) -> Path:
    """Record of exactly what the active profile changed, so switching undoes only that."""
    return root / ".claude" / "profile-state.json"


def merge(settings: dict, overlay: dict, path: tuple = ()) -> list:
    """Add `overlay` into `settings` (in place). Returns the changes actually made:
    list items that weren't there, scalars whose value differed (with the old value),
    and containers that didn't exist. Anything already present is the user's and is
    never recorded, so it's never removed."""
    changes = []
    for key, value in overlay.items():
        p = list(path) + [key]
        if isinstance(value, (dict, list)) and key not in settings:
            settings[key] = {} if isinstance(value, dict) else []
            changes.append({"path": p, "created": True})
        if isinstance(value, dict):
            changes += merge(settings[key], value, tuple(p))
        elif isinstance(value, list):
            for item in value:
                if item not in settings[key]:
                    settings[key].append(item)
                    changes.append({"path": p, "item": item})
        elif settings.get(key) != value:
            changes.append({"path": p, "had": key in settings, "old": settings.get(key)})
            settings[key] = value
    return changes


def undo(settings: dict, changes: list) -> None:
    """Revert `changes` recorded by merge() (in place), newest first."""
    for change in reversed(changes):
        parent = settings
        for key in change["path"][:-1]:
            parent = parent.get(key) if isinstance(parent, dict) else None
            if parent is None:
                break
        key = change["path"][-1]
        if not isinstance(parent, dict) or (key not in parent and "had" not in change):
            continue
        if "item" in change:
            if change["item"] in parent[key]:
                parent[key].remove(change["item"])
        elif change.get("created"):
            if not parent[key]:
                del parent[key]
        elif change["had"]:
            parent[key] = change["old"]
        else:
            parent.pop(key, None)


def ordered(settings: dict) -> dict:
    """Keep `env` and `permissions` near the top for readability."""
    order = ["$schema", "env", "permissions"]
    return {k: settings[k] for k in order if k in settings} | {k: v for k, v in settings.items() if k not in order}


def current_state(settings: dict, state: dict | None, all_profiles: dict[str, dict]) -> dict:
    """The recorded state, or — for a repo without one — assume the declared profile's
    overlay was applied in full on top of the base settings."""
    if state:
        return state
    name = settings.get("env", {}).get("CLAUDE_TEMPLATE_PROFILE")
    if name not in all_profiles:
        return {"profile": None, "changes": []}
    changes = [{"path": p, "item": item} if item is not _SCALAR else {"path": p, "had": False, "old": None}
               for p, item in _leaves(all_profiles[name]["settings"])]
    return {"profile": name, "changes": changes}


_SCALAR = object()


def _leaves(overlay: dict, path: tuple = ()):
    for key, value in overlay.items():
        p = list(path) + [key]
        if isinstance(value, dict):
            yield from _leaves(value, tuple(p))
        elif isinstance(value, list):
            for item in value:
                yield p, item
        else:
            yield p, _SCALAR


def apply_profile(settings: dict, name: str, all_profiles: dict[str, dict],
                  state: dict | None = None) -> tuple[dict, dict]:
    """Undo what the active profile changed, apply `name`. Returns (settings, new state)."""
    if name not in all_profiles:
        raise SystemExit(f"unknown profile '{name}'. Available: {', '.join(all_profiles)}")
    result = json.loads(json.dumps(settings))
    undo(result, current_state(settings, state, all_profiles)["changes"])
    changes = merge(result, json.loads(json.dumps(all_profiles[name]["settings"])))
    return ordered(result), {"profile": name, "changes": changes}


def agent_files(root: Path) -> list[Path]:
    return sorted((root / ".claude" / "agents").glob("*.md"))


def agent_model(path: Path) -> str:
    m = re.search(r"^model:\s*(\S+)\s*$", path.read_text(encoding="utf-8"), re.M)
    return m.group(1) if m else ""


def set_agent_model(path: Path, model: str) -> None:
    text = path.read_text(encoding="utf-8")
    new, n = re.subn(r"^model:\s*\S+\s*$", f"model: {model}", text, count=1, flags=re.M)
    if n == 0:
        raise SystemExit(f"{path}: no 'model:' line in frontmatter")
    path.write_text(new, encoding="utf-8", newline="\n")


def check_model(model: str) -> str:
    if not MODEL_RE.match(model):
        raise SystemExit(f"'{model}' is not a model alias, claude-* ID or 'inherit'")
    return model


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", type=Path, default=ROOT, help=argparse.SUPPRESS)
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("show")
    p = sub.add_parser("profile")
    p.add_argument("name")
    m = sub.add_parser("models")
    m.add_argument("--strong")
    m.add_argument("--standard")
    m.add_argument("--all")
    m.add_argument("--fallback", help="comma-separated chain, max 3; empty string removes it")
    args = parser.parse_args(argv)
    root = args.root
    sp = settings_path(root)
    settings = load_json(sp)

    if args.cmd == "show":
        print(f"profile: {settings.get('env', {}).get('CLAUDE_TEMPLATE_PROFILE', '(none)')}")
        print(f"fallbackModel: {settings.get('fallbackModel', '(unset)')}")
        for path in agent_files(root):
            tier = "strong" if path.stem in STRONG_AGENTS else "standard"
            print(f"  {path.stem:<20} {tier:<9} {agent_model(path)}")
        return 0

    if args.cmd == "profile":
        stp = state_path(root)
        state = load_json(stp) if stp.exists() else None
        new_settings, new_state = apply_profile(settings, args.name, profiles(root), state)
        save_json(sp, new_settings)
        save_json(stp, new_state)
        print(f"Applied profile '{args.name}'. Review with: git diff .claude/")
        return 0

    strong = check_model(args.all or args.strong) if (args.all or args.strong) else None
    standard = check_model(args.all or args.standard) if (args.all or args.standard) else None
    if not (strong or standard or args.fallback is not None):
        parser.error("models: pass --strong, --standard, --all and/or --fallback")
    for path in agent_files(root):
        model = strong if path.stem in STRONG_AGENTS else standard
        if model:
            set_agent_model(path, model)
    if args.fallback is not None:
        chain = [check_model(x.strip()) for x in args.fallback.split(",") if x.strip()]
        if "inherit" in chain:
            raise SystemExit("'inherit' is not a fallback model; name an alias or ID")
        if len(chain) > 3:
            raise SystemExit("fallbackModel keeps at most 3 models")
        if chain:
            settings["fallbackModel"] = chain
        else:
            settings.pop("fallbackModel", None)
        save_json(sp, settings)
    print("Updated. Check with: python scripts/configure.py show")
    return 0


if __name__ == "__main__":
    sys.exit(main())
