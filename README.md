<p align="center">
  <img alt="Vibe Wrap — end-of-session wrap-up that reads the trail your toolkit already left" src="https://626labs.dev/assets/brand/plugins/vibe-wrap-banner-1500x500.png" />
</p>

# Vibe Wrap

**Sessions wrap themselves when the trail is already there.**

[![stable](https://img.shields.io/github/v/tag/estevanhernandez-stack-ed/vibe-wrap?label=stable&color=17d4fa)](https://github.com/estevanhernandez-stack-ed/vibe-wrap/tags)

## What it does

End-of-session wrap-up for Claude Code — it reads the breadcrumb trail your toolkit already left instead of cold-reconstructing from `git log` and memory. One gesture at session end gives you a clean handoff: what shipped, what's still uncommitted, what's still unpushed, and a written record you can read, share, or paste into a status update. It's not a prompt for the next agent — it's a "what we shipped today" summary.

It's multi-repo aware: it surfaces what shipped across every repo the session touched, then gates commit + push on the current repo only — read wide, mutate narrow.

## How it works

End-of-session reconstruction is expensive when work hasn't been committed in steady passes. Vibe Wrap solves that with a **breadcrumb pattern** — sibling vibe plugins already write structured session-logs, friction, and wins as part of their own self-evolution loop, so Vibe Wrap reads that trail at session end. Zero coupling, zero extra instrumentation required.

**Commands:**

- `/vibe-wrap` — the main end-of-session wrap. Reads the trail + git state + your decision log, renders a six-section summary to `docs/session-wraps/<ts>.md` and inline, then runs interactive commit / push / decision-log / dashboard-bridge gates.
- `/vibe-wrap:status` — read-only, mid-session: what trail's been picked up so far.
- `/vibe-wrap:plant` — internal; siblings (or any tool) drop a richer breadcrumb at command-start. No-op-safe.
- `/vibe-wrap:evolve-wrap` — self-evolution (Pattern #1): reads Vibe Wrap's own session + friction logs and proposes plugin improvements. Never auto-applies.

**Bumper-lanes invariant.** Every gate defaults to no-action. Nothing commits, pushes, or writes without an explicit yes — and secret-pattern matches (`.env*`, `*.pem`, `*.key`, `*token*`) require a second confirmation. The wrap surfaces state; you decide what happens to it.

**Decision log — pluggable.** Vibe Wrap reads and (optionally) appends to a decision log. Four backends, chosen on first run or via config: **Markdown file** (default), **JSONL file**, **626Labs MCP** (when reachable), or **disabled**. Useful for any builder, not just 626Labs — the dashboard bridge is an MCP-only, threshold-gated extra.

## Validated on

Dogfooded on the family's own build sessions — Vibe Wrap wrapped the very work that shipped the other plugins, reading the real breadcrumb trail they left.

## Install

**Stable (recommended) — via the marketplace:**

```text
/plugin marketplace add estevanhernandez-stack-ed/vibe-plugins
/plugin install vibe-wrap@vibe-plugins
```

**Canary — track this repo's `main`:**

```text
/plugin install vibe-wrap@estevanhernandez-stack-ed/vibe-wrap
```

Requirements: Claude Code (CLI / VS Code / JetBrains), Python 3.11+ and Git on `PATH` (pure stdlib — no third-party dependencies). The 626Labs MCP is optional (one of four decision-log backends).

## For plugin authors

Want your tool to enrich the trail? See the breadcrumb contract at [`plugins/vibe-wrap/skills/wrap/references/breadcrumb-contract.md`](plugins/vibe-wrap/skills/wrap/references/breadcrumb-contract.md). Vibe Wrap already reads any plugin that writes the `~/.claude/plugins/data/<name>/sessions/` + `friction.jsonl` convention — `:plant` is the opt-in for richer attribution.

## Part of the Vibe ecosystem

Part of the **[Vibe Plugins](https://github.com/estevanhernandez-stack-ed/vibe-plugins)** marketplace from [626 Labs](https://626labs.dev) — foundations and process pillars for AI-assisted creation. Wrap is the session-close pillar: it pairs with [Vibe Insights](https://github.com/estevanhernandez-stack-ed/vibe-insights) (close one session cleanly; read across all of them).

```text
/plugin marketplace add estevanhernandez-stack-ed/vibe-plugins
```

## License

MIT — *Imagine Something Else.*
