# Changelog

All notable changes to vibe-wrap are documented here. Format loosely follows
[Keep a Changelog](https://keepachangelog.com/); versions follow semver.

## [0.2.0] — 2026-05-23

### Added — multi-repo session awareness (read wide, mutate narrow)

Fixes the headline finding from the first canary soak
(`docs/soak/2026-05-23-first-self-wrap.md`, finding #1): **single-repo
blindness.** v0.1.0's wrap was scoped to the current working directory's git
repo only, but a real session often spans many repos — the first self-wrap
session touched seven, and the wrap saw just one of them.

The fix splits the wrap into a wide read path and narrow mutating gates:

- **Read wide.** New `multi-repo-state.py` aggregator discovers sibling git
  repos under the scan root (default = the parent of the current repo) and
  reports per-repo state for every repo that had ≥1 commit in the session
  window. A cheap `git rev-parse` gate skips non-git dirs before any `git log`
  runs, so a ~70-dir scan root stays fast. Zero-in-window repos are dropped;
  commits shown per repo are capped (default 10) with a truncation note.
- **Mutate narrow.** The commit gate, push gate, decision-log write, and
  bridge stay scoped to the **current repo only** — the one you're standing
  in. Sibling repos' uncommitted/unpushed state is surfaced **read-only**
  under `gates.other_repos`; vibe-wrap never offers to commit or push a repo
  it isn't in.
- **"What shipped"** now leads with `Across N repos this session (M commits
  total): …` plus a per-repo subsection (repo name, commit count, recent
  commits). **"Still unpushed"** lists any sibling ahead of its remote as
  informational-only.

### Added — new flags on `render-wrap.py`

- `--repos <p1,p2,...>` — explicit repo set; bypasses discovery.
- `--repo-roots <dir>` — override the discovery scan root (default = parent of cwd).
- `--no-multi-repo` — fall back to the v0.1.0 cwd-only shape.

### Changed

- `git-state.py` gains a `--repo <path>` flag and an importable
  `collect_state(session_start, cwd)` core, so the multi-repo wrapper reuses
  the single-repo logic per repo. The existing `python git-state.py` entry
  point is unchanged.
- `render-wrap.py` reads git state through the multi-repo aggregator; the
  gate-state JSON gains a `multi_repo` discovery summary and a
  `gates.other_repos` read-only array.
- Wrap template header notes the read-wide/mutate-narrow boundary.

### Documentation

- `references/gate-design.md` gains a "Read wide, mutate narrow" section
  documenting the boundary, discovery bounds, and the new flags.
- `skills/wrap/SKILL.md` describes the multi-repo behavior and flags.

### Tests

- `tests/test_multi_repo_state.py` — stdlib `unittest` harness over real
  throwaway git repos: multi-repo aggregation, current-first ordering,
  discovery filtering (out-of-window sibling excluded, non-git dir skipped),
  `--repos` override, `--no-multi-repo` fallback, commit cap, and a
  single-repo regression guard for `git-state.py`.

_Credit: first canary self-wrap soak surfaced the single-repo blindness as
the P1 finding. This release closes it; soak findings #2–#4 remain queued for
a later cycle._

## [0.1.0] — 2026-05-23

Initial canary release. Session wrap-up that reads the breadcrumb trail
sibling vibe plugins already left rather than cold-reconstructing the session.

- Reads breadcrumbs, sibling session-logs / friction / wins, git state, and a
  pluggable decision-log backend (Markdown / JSONL / 626Labs MCP / disabled).
- Renders a six-section markdown wrap doc (What shipped, Decisions logged,
  Friction signals, Still uncommitted, Still unpushed, Session bounds) to
  `docs/session-wraps/<ts>.md` (fallback `.vibe-wrap/wraps/<ts>.md`).
- Four interactive gates (commit, push, decision-log write, dashboard bridge)
  under the bumper-lanes invariant — every gate defaults to no-action with a
  clear skip path; secret-pattern matches require an extra confirmation;
  force-push, mass-edits, and irreversible actions are never offered.
- SessionEnd nudge hook + session-logger + friction-logger for the
  self-evolving framework.

[0.2.0]: https://github.com/estevanhernandez-stack-ed/vibe-wrap
[0.1.0]: https://github.com/estevanhernandez-stack-ed/vibe-wrap
