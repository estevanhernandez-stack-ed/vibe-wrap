# vibe-wrap v0.1.0 — first canary soak (self-wrap)

> The first real-world run of vibe-wrap: invoked on the very session that built it
> (2026-05-23, in `vibe-plugins`). Findings feed the first `/vibe-wrap:evolve-wrap` cycle.

## What worked

- `render-wrap.py` ran clean against a real repo — produced the full six-section wrap + the `VIBE-WRAP-GATE-STATE` JSON, no crash.
- Git "what shipped" was accurate (the 8 `vibe-plugins` commits in-window, most-recent-first, truncation note).
- Commit gate correctly flagged the 2 untracked dirs; push gate correctly read at-parity; unusual-git-state correctly false.
- Session bounds + gate-state structure all rendered as specified.

## Findings for v0.2 (evolve-wrap)

1. **Single-repo blindness (P1 — the headline).** The wrap is scoped to the cwd's git repo. This session spanned **seven repos** (vibe-plugins + the cart/keystone/iterate/doc/vibe-sec/vibe-wrap solo repos), but the wrap showed only the 8 vibe-plugins commits — it missed the bulk of the day's work (the vibe-sec stub→stable arc, four solo-repo renames, the vibe-wrap solo repo itself). The breadcrumb pattern solves cross-*plugin* attribution, not cross-*repo* git work. v0.2 needs multi-repo session awareness, or at minimum a "this session also touched: <repos>" line derived from breadcrumbs/decisions.

2. **Decision-log empty from the standalone script (P2).** `mcp.py` can't invoke `mcp__626Labs__*` from a plain Python process — those are agent tool-calls. So a script-only run reports "decision-log backend not configured" even when MCP is live and decisions were logged. The SKILL/agent must own the MCP read and inject results. Either make the SKILL body unambiguously the MCP driver, or have the script emit "decisions: resolved by the SKILL via MCP" rather than the misleading "not configured."

3. **Breadcrumb bootstrap-empty (expected, but instructive).** Zero breadcrumbs — no sibling planted because vibe-wrap didn't exist during the work. The git fallback did all the lifting, which is exactly why finding #1 bites so hard. Once siblings adopt `:plant`, future sessions improve; the git layer still needs to be multi-repo to be trustworthy on its own.

4. **Wrap-doc location in public repos (P3).** The default write to `<repo>/docs/session-wraps/` drops a session log into whatever repo you're in — including a public one (here, vibe-plugins). Consider defaulting to the gitignored `.vibe-wrap/wraps/` when the repo has a public remote, or make the location an explicit config.

## Verdict

The deterministic core is solid and crash-free on a real repo — but v0.1.0's honest coverage is single-repo, and the richest signal (decisions) only materializes through the SKILL path, not the script alone. Single-repo awareness is the v0.2 headline. The plugin works; it just needs to see wider.
