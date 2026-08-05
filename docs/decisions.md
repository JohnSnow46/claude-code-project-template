# Decisions — index

This file is an **index and usage log**, not content. Full ADR text lives one-per-file in
`docs/adr/ADR-NNNN.md`. Never write ADR content directly here — see
[docs/README.md](README.md) for why (context-window discipline).

## Index

One line per ADR: number, link, one-sentence summary. Newest at the bottom.

- [ADR-0001](adr/ADR-0001-example.md) — Example ADR showing the Context → Decision →
  Consequences format. Delete once you have real ADRs.

## ADR Notes

Per-task usage log, newest entry at the top. The main/orchestrating thread appends one
entry here after a **normal/deep** mode task finishes (all agents in the chain done) — see
the "Using the docs" section in `CLAUDE.md`, step 6. Skip in fast mode unless an ADR was
actually used.

Template for a new entry:

```markdown
### YYYY-MM-DD — <short task description>
- ADRs used: ADR-NNNN (<one-line impact on the implementation>)
- ADRs read but not used: ADR-NNNN (<why it didn't apply>)
```

<!-- Newest entries go directly below this line. -->
