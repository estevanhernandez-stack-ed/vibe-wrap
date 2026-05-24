# Gate design

> **Audience:** vibe-wrap maintainers + builders reviewing the wrap flow.
> **Status:** four gates locked for v0.1.0. Bumper-lanes invariant load-bearing.

vibe-wrap surfaces actions but never takes them autonomously. Every gate is interactive, defaults to no-action, and has a clear skip path. The gates are bumpers, not walls — and definitely not gutters.

## The bumper-lanes invariant

The wrap doc itself is always produced. The gates are layered on top. The contract:

1. **The wrap doc lands on disk (and inline) regardless of which gates the user accepts or skips.** Gates never block doc production.
2. **Every gate defaults to no-action.** Pressing enter or typing `n` at any prompt is non-destructive.
3. **Every gate has a clearly labeled skip path.** Users can decline any individual gate without aborting the wrap flow.
4. **Force-modes, mass-edits, and irreversible blast-radius actions are never offered.** No `git push --force`, no mass-edit of decision log entries, no auto-stage of unrelated files.
5. **Secret-pattern matches require an additional confirmation step.** See `secret-patterns.md` for the matching rules and warning UX.

The invariant is enforced at the SKILL level. Each of the four gates inherits these defaults; per-gate rules below extend (never override) them.

## Read wide, mutate narrow (v0.2.0 — multi-repo session awareness)

> Added in v0.2.0 to fix the first-soak headline finding: **single-repo blindness.** A real session often spans many repos (the first soak touched seven); v0.1.0's wrap only ever saw the cwd's repo.

The fix splits the wrap into two surfaces with a hard boundary:

- **The READ path is wide.** `multi-repo-state.py` discovers sibling git repos under the scan root (default = the parent of the current repo) and reports per-repo state for every repo that had ≥1 commit in the session window. "What shipped" leads with `Across N repos this session: …` and a per-repo subsection; "Still unpushed" lists any sibling ahead of its remote — read-only.
- **The MUTATING gates stay narrow.** The commit gate, push gate, decision-log write, and bridge all act on the **current repo only** — the one repo you're actually in. You never commit or push a repo from a wrap run against a different repo.

Why this boundary is the safe design: committing or pushing a repo you aren't standing in is a high-blast-radius action with no good default — you can't reason about another repo's staging intent, branch state, or hook side effects from a wrap doc. So vibe-wrap *surfaces* sibling dirty state (so you know it exists) but *never offers to act on it*. The gate-state JSON carries sibling read-only state under `gates.other_repos`; that array is informational and has no `eligible` field, because it is never a gate.

**The invariant, restated for multi-repo:** the wrap doc reads as wide as the session went; the gates reach exactly as far as the repo you're in.

### Discovery bounds (keep the read cheap)

The scan root may hold ~70 directories. To stay fast and relevant:

- A cheap `git rev-parse` gate decides whether each child is a repo at all **before** any `git log` runs. Non-git dirs are skipped.
- Repos with zero in-window commits are dropped from the output (the current repo is the one exception — always kept, since it owns the gates).
- Commits shown per repo are capped (default 10); the true count is still reported, with a truncation note.

### Flags (on `render-wrap.py`)

| Flag | Default | Purpose |
|---|---|---|
| `--repos <p1,p2,...>` | (off) | Explicit repo set — bypasses discovery entirely. Each path is read (filtered to git repos), plus the current repo. |
| `--repo-roots <dir>` | parent of cwd | Override the discovery scan root. |
| `--no-multi-repo` | off | Fall back to cwd-only (the v0.1.0 shape). |

## Gate 1 — Commit gate

**When it appears:** uncommitted files exist (`git status --porcelain` returns ≥1 line).

**When it's skipped:** clean working tree (no prompt at all).

### Default behavior

```
uncommitted files (3):
  M  drafts/vibe-wrap/process-notes.md
  ?? drafts/vibe-wrap/scratch.txt
  M  packages/vibe-wrap/skills/wrap/SKILL.md

commit these? [y/N]
```

Default `N`. Pressing enter skips. Typing `y` advances to message-draft.

### Message draft

When user accepts:

```
drafted commit message from wrap summary:

  feat(vibe-wrap): item 1 — scaffold plugin tree + manifest + contract refs

  Captures the structural skeleton for the v0.1.0 ship: directory tree
  per spec § File Structure, plugin.json, 7 SKILL.md frontmatter stubs,
  4 reference docs at full content.

accept message? [y/N/edit]
```

| Choice | Action |
|---|---|
| `y` | Stage the listed files + commit with the drafted message. |
| `N` (default) | Skip the commit entirely. Returns to the next gate. |
| `edit` | Drop user into `$EDITOR` with the drafted message; commits with whatever they save. Empty save aborts. |

### Secret-pattern path

When any uncommitted file matches a secret pattern (`.env*`, `*credentials*`, `*.pem`, `*.key`, `*token*`, `id_rsa`, `id_ed25519`, `*.kdbx` — see `secret-patterns.md` for the full list and matching rules):

```
WARNING — uncommitted files match common-secret patterns:
  M  .env.local
  M  config/credentials.yml

if you commit these, secrets may end up in git history.
commit despite secret-pattern match? [y/N]
```

Additional confirmation step. Default `N`. Even if the user accepted the main commit gate, this extra prompt fires per match. Typing `n` (or pressing enter) excludes the matched files from the commit; typing `y` includes them. The wrap doc records that the user was warned.

### What's never offered

- **Auto-stage of unrelated files.** Only the files surfaced in the wrap are staged. `git add -A` is not how this works.
- **`--no-verify` to skip pre-commit hooks.** If hooks fail, the commit fails — surface the failure inline.
- **Empty commits.** If staging produces no diff (all files were already committed elsewhere), abort with a one-line note.
- **Amending the previous commit.** vibe-wrap creates new commits only. Amending is the user's gesture, not vibe-wrap's.

## Gate 2 — Push gate

**When it appears:** local branch is ahead of its tracked remote (`git rev-list HEAD..@{u}` returns ≥1).

**When it's skipped:**

- No tracked remote (`@{u}` lookup fails) → silent skip, no prompt.
- Branch is at parity with remote → silent skip.
- Branch has diverged (commits both ahead and behind) → surfaced as state to resolve manually, **no push prompt**.

### Default behavior

```
3 commits ahead of origin/main.
  abc1234 feat(vibe-wrap): scaffold plugin tree
  def5678 feat(vibe-wrap): guide SKILL + voice rules
  ghi9012 feat(vibe-wrap): session-logger + friction-logger

push to origin/main? [y/N]
```

Default `N`. Pressing enter skips.

### Multi-remote path (locked answer to spec Open Issue #4)

When the current branch has an upstream AND additional remotes exist:

1. Name the upstream of the current branch first. Show the same prompt above.
2. After the user answers (y or n), offer one follow-up:

```
push to a different remote? [y/N]
```

If `y`: list available remotes (excluding the upstream just handled), let user pick one + branch.
If `N` (default): close the gate.

### What's never offered

- **`git push --force` or `--force-with-lease`.** Diverged branches surface as a state to resolve manually. vibe-wrap never offers force-push, even when the user has explicitly opted into a "push everything" flag (no such flag exists).
- **Push to all remotes.** One remote per push gesture. Multi-remote is a sequence of explicit gestures.
- **Push of a different branch.** vibe-wrap pushes the current branch only. Cross-branch push is the user's gesture in the shell.

## Gate 3 — Decision-log write gate

**When it appears:** active backend is anything other than `disabled`. Active backend = the resolved decision-log backend per `decision-log-backends.md > Config precedence`.

**When it's skipped:** active backend is `disabled` → no prompt at all.

### Default behavior

```
append a session-end decision to your <backend-name> log? [y/N]
```

| Active backend | Prompt phrasing |
|---|---|
| `file-md` | `append a session-end decision to your Markdown decision log? [y/N]` |
| `file-jsonl` | `append a session-end decision to your JSONL decision log? [y/N]` |
| `626labs-mcp` | `append a session-end decision to the 626Labs Dashboard? [y/N]` |
| `disabled` | (no prompt — gate skipped) |

Default `N`. Pressing enter skips.

When user accepts: the decision body is drafted from the wrap summary excerpt + a link to the wrap doc + the project tag (bound 626Labs project ID for MCP, repo name for file backends, or `null` for unbound). Append uses the active backend's `append()` method per the contract in `decision-log-backends.md`.

### Failure modes

- **Active backend `is_reachable()` returns False at gate time** (MCP just dropped, file became unwritable) → surface a one-line error, fall back to no-op, continue to next gate. Don't abort the wrap flow.
- **Append returns `{"ok": False}`** → surface the error string, continue. The wrap doc still lands.

### What's never offered

- **Editing or deleting prior decisions.** vibe-wrap is a writer, not a curator. Read-mostly contract.
- **Mass-append of multiple session decisions.** One session, one optional decision append. Cross-session digests are `/evolve-wrap-cycle` work, not v0.1.0.

## Gate 4 — Dashboard bridge gate

**When it appears:** active backend is `626labs-mcp` AND the threshold (per `spec.md > Decision 3`) fires. Threshold = at least one of:

- A decision was logged this session via the decision-log MCP (the recognized one is the 626Labs dashboard, `mcp__626labs-cloud__manage_decisions`) — detected during the decision-log read step.
- The session window covers >2 commits.
- User passed the `--bridge` flag.

**When it's skipped:**

- Active backend is anything other than `626labs-mcp` → silent skip. Bridge is MCP-specific.
- Backend is `626labs-mcp` but threshold not met → silent skip.

### Default behavior

```
session crossed the strategic threshold (3 commits, 1 decision logged).

bridge strategic context to the dashboard's Architect AI? [y/N]
```

Default `N`. Pressing enter skips.

When user accepts: call the auto-detected decision-log MCP's bridge tool — the recognized one is the 626Labs dashboard (`mcp__626labs-cloud__bridge_context_to_architect`) — with the wrap summary as context. If the MCP is unreachable at gate time, surface a one-line note and skip silently. The MCP is optional; absence is never an error.

### What's never offered

- **Auto-bridge.** Even when threshold fires, the bridge is opt-in per gesture. Never autonomous.
- **Bridge to non-Architect destinations.** v0.1.0 only knows about `bridge_context_to_architect`. Future bridge contracts (Linear, Notion, custom MCPs) extend this gate; the v0.1.0 surface is one Architect call.
- **Bridge of edited / abridged context.** The bridge sends the wrap summary as-is. Editing the bridged content is `/evolve-wrap` work; for v0.1.0 the user can decline the bridge and craft a custom message via the dashboard's Architect chat instead.

## Gate-summary table

| Gate | Trigger | Scope | Default | Skip path | Extra confirmation |
|---|---|---|---|---|---|
| 1 — Commit | Uncommitted files exist | current repo only | `N` | Press enter / type `n` | Required for secret-pattern matches |
| 2 — Push | Local ahead of remote | current repo only | `N` | Press enter / type `n` | None (force-push never offered) |
| 3 — Decision-log write | Active backend ≠ `disabled` | current repo only | `N` | Press enter / type `n` | None |
| 4 — Dashboard bridge | Backend = `626labs-mcp` AND threshold met | current repo only | `N` | Press enter / type `n` | None |
| — `other_repos` | Sibling repo has commits / dirty state | read-only | n/a | n/a — **never a gate** | Informational only; vibe-wrap never commits/pushes a sibling repo |

## See also

- **Bumper-lanes invariant origin** — `spec.md > vibe-wrap:guide`. The guide SKILL enforces this contract across every other vibe-wrap SKILL.
- **Secret-pattern rules** — `secret-patterns.md` (sibling of this doc).
- **Threshold rule** — `spec.md > Decision 3`.
- **Backend contracts** — `decision-log-backends.md` (sibling of this doc).
