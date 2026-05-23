# Vibe Wrap

> Sessions wrap themselves when the trail is already there.

End-of-session wrap-up for Claude Code — it reads the breadcrumb trail your toolkit already left instead of cold-reconstructing from `git log` and memory. One gesture at session end gives you a clean handoff: what shipped, what's still uncommitted, what's still unpushed, and a written record you can read, share, or paste into a status update.

It's not a prompt for the next agent. It's a "what we shipped today" summary.

## Why it exists

End-of-session reconstruction is expensive when work hasn't been committed in steady passes. Vibe Wrap solves that with a **breadcrumb pattern** — sibling vibe plugins already write structured session-logs, friction, and wins as part of their own self-evolution loop, so Vibe Wrap reads that trail at session end. Zero coupling, zero extra instrumentation required.

## Commands

- `/vibe-wrap` — the main end-of-session wrap. Reads the trail + git state + your decision log, renders a six-section summary to `docs/session-wraps/<ts>.md` and inline, then runs interactive commit / push / decision-log / dashboard-bridge gates.
- `/vibe-wrap:status` — read-only, mid-session: what trail's been picked up so far.
- `/vibe-wrap:plant` — internal; siblings (or any tool) drop a richer breadcrumb at command-start. No-op-safe.
- `/vibe-wrap:evolve-wrap` — self-evolution (Pattern #1): reads Vibe Wrap's own session + friction logs and proposes plugin improvements. Never auto-applies.

## Bumper-lanes invariant

Every gate defaults to no-action. Nothing commits, pushes, or writes without an explicit yes — and secret-pattern matches (`.env*`, `*.pem`, `*.key`, `*token*`) require a second confirmation. The wrap surfaces state; you decide what happens to it.

## Decision log — pluggable

Vibe Wrap reads and (optionally) appends to a decision log. Four backends, chosen on first run or via config: **Markdown file** (default), **JSONL file**, **626Labs MCP** (when reachable), or **disabled**. It's a marketplace plugin — useful for any builder, not just 626Labs. The 626Labs dashboard bridge is an MCP-only, threshold-gated extra.

## Install

**Canary (this repo, latest `main`):**

```
/plugin marketplace add estevanhernandez-stack-ed/vibe-wrap
/plugin install vibe-wrap
```

**Stable** ships via the aggregated [626Labs marketplace](https://github.com/estevanhernandez-stack-ed/vibe-plugins) once a tagged release is pinned there.

## Requirements

- Claude Code (CLI / VS Code / JetBrains).
- Python 3.11+ and Git on `PATH`. Pure stdlib — no third-party dependencies.
- 626Labs MCP optional (one of four decision-log backends).

## For plugin authors

Want your tool to enrich the trail? See the breadcrumb contract at [`plugins/vibe-wrap/skills/wrap/references/breadcrumb-contract.md`](plugins/vibe-wrap/skills/wrap/references/breadcrumb-contract.md). Vibe Wrap already reads any plugin that writes the `~/.claude/plugins/data/<name>/sessions/` + `friction.jsonl` convention — `:plant` is the opt-in for richer attribution.

## License

MIT © 626Labs LLC
