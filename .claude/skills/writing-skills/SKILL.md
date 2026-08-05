---
name: writing-skills
description: Use when creating a new skill or agent in this repo, or editing an existing one's frontmatter/description/instructions.
---

# Writing Skills (and Agents)

Condensed from [obra/superpowers](https://github.com/obra/superpowers)' `writing-skills`
(MIT-adjacent, credited — not copied verbatim). Full methodology there includes
pressure-testing with subagents; this version keeps the rules that matter most for a
small, hand-maintained set.

## The description is the single highest-leverage line

The `description` field is what decides whether this skill/agent gets used at all — and,
if written wrong, actively works against you.

- **Describe WHEN to use it, never WHAT it does or HOW.** A description that summarizes
  the workflow becomes a shortcut the model follows instead of reading the actual body —
  tested behavior, not a style preference. A skill whose description says "reviews a diff
  and runs two passes" can cause the model to do one pass and skip reading the flowchart
  that says two.
- Start with "Use when..." and name concrete triggers, symptoms, error messages — words
  someone would actually search for.
- Third person. Keep it tight; every word here loads into context on every turn for
  model-invoked skills.

```yaml
# Bad — summarizes the workflow, becomes a shortcut
description: Reviews code for security issues, checking auth, injection, and secrets

# Good — only the trigger
description: Use before shipping code that handles auth, user input, secrets, or external data
```

## Match the form of guidance to the failure it prevents

Superpowers' key finding: the wrong *form* of guidance can make a failure *worse*, not
better. Diagnose the failure type before choosing how to write the rule.

| The failure looks like... | Use this form | Not this |
|---|---|---|
| Knows the rule, skips it under pressure (a discipline failure) | A flat prohibition + a rationalization table ("excuse → reality") | Soft language ("prefer...", "consider...") |
| Complies, but the output has the wrong shape | A positive recipe: state what the output IS, its parts, in order | A list of "don't"s |
| Omits a required element from something already being produced | A structural slot/field in the template itself | A prose reminder near the template |
| Behavior should depend on a condition | A conditional keyed to something observable ("if X exists, do Y") | An unconditional rule with exemption clauses bolted on |

Two traps regardless of which form you pick: **no nuance clauses** ("don't do X unless it
matters" reopens the exact negotiation you were trying to close), and **exemptions don't
scope** ("this doesn't apply to Y" still leaks into Y in practice — restructure instead).

## Keep it short — every line is a recurring cost

Once loaded, a skill's content stays in context for the rest of the session. Target:

- Skills that load often (referenced constantly): well under 200 words
- Everything else: aim under ~500 words, still concise

Move detail to a separate file (`reference.md`, `scripts/`) linked from `SKILL.md` rather
than inlining it — see [Add supporting files](https://code.claude.com/docs/en/skills#add-supporting-files).

## Before shipping

- Read 2-3 similar existing skills/agents in this repo first — match frontmatter shape,
  section structure, and tone (see the `prompt-engineer` agent, which does this for you if
  you delegate to it).
- Say out loud what specific failure this skill/agent prevents. If you can't name one,
  it's probably not needed yet.
- Give it a quick real test: a fresh session, a prompt that should trigger it, and one
  that shouldn't — confirm it fires (or doesn't) as intended before considering it done.
