# Usage guide

Step-by-step walkthrough for adopting this template in a real project. `README.md` is the
reference (tables, attribution); this file is the narrative "do this, then this."

## 1. Copy it into your project

```bash
cp -r CLAUDE.md docs .claude /path/to/your-project/
cd /path/to/your-project
```

If your project already has a `CLAUDE.md`, merge by hand instead of overwriting — keep
whatever it already had right, add what this template adds.

## 2. Fill in `CLAUDE.md`

Work through it top to bottom; each section is a placeholder to replace, not boilerplate
to leave in:

1. **Title/one-liner** — what the project does, stack, how it's structured.
2. **Docs table** — one row per area doc you'll actually create (see step 5). Leave it
   empty if you're not using the ADR/docs system at all (see step 6, "trimming").
3. **Tiering table signals** — the columns (areas touched, new business rule, schema
   change, security touch) are already generic; you usually don't need to edit the table
   itself. Do fill in the **priority order** line right below the mandatory rules — this
   is the one line that most changes agent behavior day to day (e.g. "working feature >
   fast iteration > consistency" for a prototype, vs. "correctness > working feature >
   consistency" for something regulated).
4. **Critical constraints** — leave empty until you actually have one. Don't invent
   constraints speculatively; add a line here the first time a real invariant gets
   violated or almost does.
5. **Global conventions, Commands, Environment** — the mechanical stuff: naming, how to
   build/test/run, what review process you use. Claude can't guess these from the repo
   reliably, so they're worth getting right early.
6. **Response language** (optional) — if you want every agent responding in a specific
   language, add one line to CLAUDE.md's Global conventions (e.g. "Respond in Polish").
   Every agent loads CLAUDE.md, so one line there covers all of them — don't repeat it in
   individual `.claude/agents/*.md` files.

Run `/context` after your first session to confirm `CLAUDE.md` actually loaded.

## 2b. Fill in `.claude/settings.json`

`CLAUDE.md` isn't the only file worth configuring per-project — `.claude/settings.json`
has a `permissions` object with two lists.

**`permissions.allow`** is the set of tool calls Claude can run without asking you for
approval first. `Read`, `Grep`, `Glob`, and read-only `git status`/`git diff`/`git log`
are pre-approved out of the box; everything else still prompts until you add a rule for
it. It ships with no install/test/lint/build entries, since those commands are project-
specific — add your own, using the same `Bash(<command> *)` wildcard form as the rules
already in the file:

```json
"Bash(npm install *)",
"Bash(npm test *)",
"Bash(npm run lint *)",
"Bash(npm run build *)"
```

Match these to whatever you filled into `CLAUDE.md`'s Commands section (step 2 above) —
same commands, just expressed as permission rules instead of a shell block. Don't put
`[bracketed placeholders]` inside a permission specifier the way `CLAUDE.md` does —
brackets and asterisks inside `Bash(...)` may be read literally rather than as
guidance text, so an unfilled placeholder there silently matches nothing instead of
prompting you to fill it in.

**`permissions.deny`** is checked before `allow` and wins on conflict — it's the place
for rules you want to hold even if something else grants broader access. It ships with
one guard already filled in: variants of "add everything" (`git add -A`, `--all`, `-u`,
`.`, `:/`, bare or with trailing arguments) are blocked repo-wide, backing up the
`/commit` skill's "never bulk-add" rule so it holds even outside a `/commit` turn.

### Format/lint-on-save hook (optional)

`settings.json` ships with no `hooks` key — a placeholder hook that fires on every
`Edit`/`Write` would otherwise print noise on every file write until you filled it in.
If you want your formatter/linter to run automatically after Claude edits a file, add a
`hooks` key at the top level of `settings.json` (a sibling of `permissions`), with your
stack's actual command in place of the example below:

```json
"hooks": {
  "PostToolUse": [
    {
      "matcher": "Edit|Write",
      "hooks": [
        {
          "type": "command",
          "command": "npx prettier --write ."
        }
      ]
    }
  ]
}
```

Swap `npx prettier --write .` for your stack's format/lint-on-save command (e.g. `ruff
format .`, `gofmt -w .`).

## 3. Try the pipeline on a real task

Two ways to trigger the pipeline:

- **`/feature <task description>`** — deterministic. Classifies the task against the
  tiering table, prints the chosen mode and why in one line, runs the matching agent
  chain, and — for normal/deep mode — appends the `## ADR Notes` entry to
  `docs/decisions.md` itself once the chain finishes. Use this when you want the
  classification and ADR logging to happen reliably instead of depending on the main
  thread remembering to do it.
- **Just ask normally** — the main thread classifies from the same table on its own for
  any request, without `/feature`. This still works and is fine for quick, obvious tasks;
  `/feature` exists for when you want the mode decision and ADR logging made explicit and
  guaranteed.

Don't read the agent files first — just work normally and watch what happens.

**A small task** ("add a loading spinner to the login button"):
- Expect: the main thread picks fast mode on its own, `builder` implements it,
  `reviewer-lite` gives a quick pass/fail, then invoke `/commit` yourself once it's green.
- If you see `architect` get spawned for something this small, that's a sign the tiering
  table's signals need tightening for your project — edit the table in `CLAUDE.md`.

**A medium task** ("add a password-reset flow"):
- Expect: `architect-lite` gives a 5-point plan (goal/files/solution/risks/validation)
  before `builder` starts. If it instead jumps straight to `builder`, the task probably
  didn't trip enough signals — check whether that's actually fine (many "new module"
  tasks are simpler than they sound) or whether the table needs a signal added.

**A large task** ("migrate the session store to a different backend"):
- Expect: `architect` writes an ADR to `docs/adr/ADR-NNNN.md` before any code changes,
  `builder` implements against that ADR, `reviewer` does the full audit. After the whole
  chain finishes, check `docs/decisions.md` — the main thread should have appended an
  entry to `## ADR Notes`.

If a mode never seems to trigger correctly, that's the fastest signal something in the
tiering table doesn't match how your project's tasks actually break down — treat the
table as something to tune, not something to leave as-is forever.

## 4. Working with skills

- `commit` and `feature` are user-invoked — type `/commit` or `/feature <task>` yourself.
  Claude won't run either on its own.
- `writing-skills` and `verification-before-completion` are model-invoked — Claude loads
  them automatically when relevant. You can also invoke either directly (e.g.
  `/writing-skills`) to force a read.
- `writing-tests` and `project-conventions` ship as `[fill in]` placeholders, so they're
  set `disable-model-invocation: true` for now — Claude won't auto-load a skill that's
  just brackets. Once you've filled in their content, remove the
  `disable-model-invocation: true` line from each so Claude starts loading them
  automatically again.
- If a model-invoked skill never seems to fire when it should, its `description` is
  probably too generic — see the `writing-skills` skill for how to fix that.

## 5. Growing the docs system

Once you have a real architectural decision to record:

1. Delete `docs/adr/ADR-0001-example.md` and its line in `docs/decisions.md`'s
   `## Index`.
2. Let `architect` (deep mode) write the first real one — don't hand-write ADRs yourself
   unless you're intentionally bypassing the pipeline.
3. As area docs (domain model, API layer, whatever fits your project) grow past roughly
   150 lines, add a `## Index` section near the top per the pattern in `docs/README.md`
   — this is what keeps them cheap to consult later.

## 6. Adding your own agents/skills

Delegate to `prompt-engineer`: *"Use the prompt-engineer agent to create a subagent that
[does X]."* It reads the existing agents/skills for style, applies the rules in
`writing-skills`, and hands you the finished file to review before it's saved — it won't
write the file unless you ask it to.

## 7. Trimming what you don't need

Nothing here is load-bearing for everything else. Common trims — each one also touches
`.claude/skills/feature/SKILL.md`'s chain list (step 2), which names every agent by mode.
Trimming an agent without updating that list leaves `/feature` delegating to something
that no longer exists:

- **No deep work expected** (small personal project) → delete `architect`, `reviewer`;
  keep `builder` → `reviewer-lite` as the only path, delete the tiering table from
  `CLAUDE.md` and replace with a one-line note that it's always the same chain. In
  `feature/SKILL.md`, delete the Normal and Deep rows from the chain list, or delete the
  skill entirely — with only one path, there's nothing left to classify, so `/feature`
  isn't buying you anything over just asking normally.
- **Don't want an ADR system** → delete `docs/` entirely and the "Using the docs" section
  of `CLAUDE.md`. `architect` then just designs and hands steps to `builder`, no
  file-writing. In `feature/SKILL.md`, delete step 3 ("Log ADR usage") — it appends to
  `docs/decisions.md`, which no longer exists.
- **Single-person project, no code review culture** → delete `reviewer`/`reviewer-lite`,
  have `builder` report directly to you instead. In `feature/SKILL.md`'s chain list, drop
  the reviewer/reviewer-lite step from every mode's chain.

Cut freely — a template you've pruned to fit is more useful than one you're afraid to
touch.
