# Proposed changes — vibe-wrap

> Dev-input notes for the next `/vibe-wrap:evolve-wrap` cycle. Hand-seeded between evolve runs.
> Output shape for a full evolve run is locked in [`skills/evolve-wrap/references/proposed-changes-template.md`](skills/evolve-wrap/references/proposed-changes-template.md).
> **Nothing here is applied automatically.** Each entry is a signal to weigh, not a committed change.

## 2026-05-23 — evolve signal: bring-your-own decision-log MCP

Add a config path for a user-specified decision-log MCP — let the `mcp` backend target an arbitrary server's tool names (e.g. `mcp__<their-server>__<their-log-tool>`), not only the auto-detected 626Labs dashboard (`mcp__626labs-cloud__*`). The v0.2.1 reframe made the language generic + file-fallback universal; this makes the MCP backend itself bring-your-own. Surfaced by the 2026-05-23 sweep.

status: deferred, evolve-input only.
