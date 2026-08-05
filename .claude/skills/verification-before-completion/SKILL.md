---
name: verification-before-completion
description: Use when about to claim work is complete, fixed, or passing, before committing or handing off to review — requires running the verification command and reading its output before making any success claim.
---

# Verification Before Completion

Condensed from [obra/superpowers](https://github.com/obra/superpowers)' skill of the same
name (credited, not copied verbatim).

**Core principle: evidence before claims, always.**

## The gate

```
BEFORE claiming any status ("done", "passes", "fixed", "works"):

1. IDENTIFY: what command actually proves this claim?
2. RUN it — fresh, in full, this turn.
3. READ the full output: exit code, failure count, actual result.
4. Does the output confirm the claim?
   - No  → state the real status, with the evidence.
   - Yes → state the claim, with the evidence.

Skipping any step is not verifying — it's asserting.
```

## Common claims and what actually proves them

| Claim | Requires | Not sufficient |
|---|---|---|
| Tests pass | This turn's test output: 0 failures | A previous run, "should pass" |
| Build succeeds | This turn's build output: exit 0 | Linter passing, "looks right" |
| Bug fixed | Reproducing the original symptom, then confirming it's gone | Code changed, assumed fixed |
| Ready for review/merge | The build/test command run in this session (see `builder`/`reviewer` agents) | Reading the diff and it "looking fine" |

## Red flags — stop and go run the command

- "Should work now" / "looks correct" / "probably fine"
- Satisfaction language ("Great!", "Done!") before the check has actually run this turn
- About to commit, hand off to `reviewer`, or mark a task complete without fresh output
- Trusting a subagent's own "success" report instead of checking its actual diff/output

## Why this is in the tiered pipeline

`builder` and both `reviewer`/`reviewer-lite` agents point here instead of restating this
inline — a "ready to merge" or "tests pass" verdict from either should always be backed by
a command that ran in that same turn, not an inference from reading code.
