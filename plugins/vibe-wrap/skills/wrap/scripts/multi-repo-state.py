#!/usr/bin/env python3
"""
multi-repo-state.py — multi-repo git-state aggregator for vibe-wrap.

The fix for v0.1.0's single-repo blindness (first-soak finding #1). A real
session often spans many repos; this wrapper reads WIDE — it discovers
sibling git repos and reports per-repo state for every repo that had ≥1
commit in the session window — while the mutating gates stay scoped to the
current repo only (read wide, mutate narrow).

It reuses the single-repo core from git-state.py: `collect_state(session_start,
cwd)` is imported and called once per discovered repo. The existing
single-repo entry (`python git-state.py`) keeps working unchanged.

Discovery model:
    1. The "current" repo is the cwd's repo (or --current-repo override).
    2. The scan root defaults to the PARENT of the current repo (so siblings
       living next to it are found), overridable with --repo-roots.
    3. For each immediate child dir of the scan root, a cheap `git rev-parse`
       gate decides whether it's a repo at all before any log read. Non-git
       dirs are skipped — keeps a ~70-dir scan root fast.
    4. A repo is INCLUDED only if it has ≥1 commit in the session window
       (`git log --since=<session-start>`). Zero-in-window repos are dropped
       so the output stays relevant.
    5. The current repo is always included (even with zero in-window commits)
       and flagged `is_current: true` — it owns the mutating gates.

Overrides:
    --repos <p1,p2,...>   Explicit repo set. Bypasses discovery entirely;
                          each listed path is read (filtered to git repos),
                          plus the current repo. Useful when the session
                          spanned repos in different parent dirs.
    --repo-roots <dir>    Scan root for discovery (default = parent of the
                          current repo).
    --no-multi-repo       Fall back to current-repo-only (the v0.1.0 shape,
                          wrapped in the multi-repo envelope).

Usage:
    python multi-repo-state.py [--session-start <iso-ts>]
                               [--current-repo <path>]
                               [--repos <p1,p2,...>]
                               [--repo-roots <dir>]
                               [--no-multi-repo]
                               [--max-commits <n>]

Output:
    JSON object on stdout. Schema:

        {
            "current_repo": "/abs/path/to/cwd-repo" | null,
            "scan_root": "/abs/path/parent" | null,
            "multi_repo": true,
            "repos": [
                {
                    "is_current": true,
                    "repo_label": "vibe-plugins",
                    ... (all single-repo git-state.py fields) ...,
                    "commits_in_window": 8,
                    "commits_truncated": false
                },
                ...
            ]
        }

    The `repos` list is ordered current-first, then by in-window commit
    count descending, then by repo label. Each entry's `commits` list is
    capped at --max-commits (default 10); `commits_in_window` reports the
    true count and `commits_truncated` flags when the cap clipped it.

Exit codes:
    0  — normal in every case (including "no siblings" — just the current
         repo, or an empty repos list when cwd is not a repo).
    1  — catastrophic (git CLI not on PATH).

Pure stdlib. Imports the single-repo core from git-state.py. Python 3.11+.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import sys
from pathlib import Path
from typing import Any

# Force UTF-8 on stdout/stderr — Windows defaults to cp1252.
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

SCRIPT_DIR = Path(__file__).resolve().parent
GIT_STATE_PATH = SCRIPT_DIR / "git-state.py"

DEFAULT_MAX_COMMITS = 10


def warn(msg: str) -> None:
    """One-line stderr warning."""
    sys.stderr.write(f"multi-repo-state: {msg}\n")


def _load_git_state_module() -> Any | None:
    """Import git-state.py as a module (hyphenated filename → dynamic load)."""
    if not GIT_STATE_PATH.exists():
        warn(f"git-state.py not found at {GIT_STATE_PATH}")
        return None
    try:
        spec = importlib.util.spec_from_file_location(
            "vibe_wrap_git_state", str(GIT_STATE_PATH)
        )
        if spec is None or spec.loader is None:
            warn("git-state.py spec unresolvable")
            return None
        module = importlib.util.module_from_spec(spec)
        sys.modules["vibe_wrap_git_state"] = module
        spec.loader.exec_module(module)
        return module
    except Exception as err:  # pragma: no cover - import guard
        warn(f"git-state.py import failed: {err}")
        return None


def repo_label(repo_root: str | None) -> str:
    """Human-friendly repo name — the basename of the toplevel."""
    if not repo_root:
        return "(not a git repo)"
    return Path(repo_root).name or repo_root


def discover_repos(scan_root: Path, gs: Any) -> list[str]:
    """Return toplevels of immediate child dirs of scan_root that are repos.

    Cheap `git rev-parse` gate per child via gs.is_git_repo() — non-git dirs
    are skipped before any log read, keeping a big scan root fast.
    """
    found: list[str] = []
    try:
        children = sorted(p for p in scan_root.iterdir() if p.is_dir())
    except OSError as err:
        warn(f"could not list scan root {scan_root}: {err}")
        return found
    for child in children:
        # Skip obvious non-repo noise early.
        name = child.name
        if name.startswith(".") or name in ("node_modules", "__pycache__", "venv"):
            continue
        root = gs.is_git_repo(str(child))
        if root:
            found.append(root)
    return found


def collect_repo(
    cwd: str, session_start: str | None, gs: Any, max_commits: int
) -> dict:
    """Run the single-repo core against `cwd` and add multi-repo fields."""
    state = gs.collect_state(session_start=session_start, cwd=cwd)
    commits = state.get("commits", []) or []
    in_window = len(commits)
    truncated = False
    if max_commits >= 0 and in_window > max_commits:
        state["commits"] = commits[:max_commits]
        truncated = True
    state["commits_in_window"] = in_window
    state["commits_truncated"] = truncated
    state["repo_label"] = repo_label(state.get("repo_root"))
    state["is_current"] = False
    return state


def _dedup_key(state: dict) -> str:
    """Canonical key for a repo so the same repo isn't listed twice."""
    root = state.get("repo_root")
    if root:
        return str(Path(root).resolve()).lower()
    return ""


def build_result(
    current_repo: str | None,
    scan_root: Path | None,
    repo_states: list[dict],
    multi_repo: bool,
) -> dict:
    """Assemble the final envelope. Orders current-first, then by commits."""

    def sort_key(s: dict) -> tuple:
        return (
            0 if s.get("is_current") else 1,
            -(s.get("commits_in_window", 0)),
            s.get("repo_label", ""),
        )

    repo_states.sort(key=sort_key)
    return {
        "current_repo": current_repo,
        "scan_root": str(scan_root) if scan_root else None,
        "multi_repo": multi_repo,
        "repos": repo_states,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="multi-repo-state.py",
        description="Multi-repo git-state aggregator — read wide, mutate narrow.",
    )
    parser.add_argument("--session-start", dest="session_start", default=None)
    parser.add_argument("--current-repo", dest="current_repo", default=None)
    parser.add_argument("--repos", dest="repos", default=None)
    parser.add_argument("--repo-roots", dest="repo_roots", default=None)
    parser.add_argument(
        "--no-multi-repo",
        dest="no_multi_repo",
        action="store_true",
        default=False,
    )
    parser.add_argument(
        "--max-commits",
        dest="max_commits",
        type=int,
        default=DEFAULT_MAX_COMMITS,
    )
    args = parser.parse_args()

    if shutil.which("git") is None:
        warn("git CLI not found on PATH")
        return 1

    gs = _load_git_state_module()
    if gs is None:
        return 1

    max_commits = args.max_commits if args.max_commits >= 0 else DEFAULT_MAX_COMMITS

    # Resolve the current repo (the one that owns the mutating gates).
    current_cwd = args.current_repo or str(Path.cwd())
    current_root = gs.is_git_repo(current_cwd)

    repo_states: list[dict] = []
    seen: set[str] = set()

    # Always include the current repo first (even with zero in-window commits)
    # — it owns the commit/push gates downstream.
    if current_root is not None:
        cur = collect_repo(current_cwd, args.session_start, gs, max_commits)
        cur["is_current"] = True
        repo_states.append(cur)
        seen.add(_dedup_key(cur))
    else:
        # cwd isn't a repo. Still emit a current entry for the renderer so
        # the "not a git repo" state surfaces; mark it current.
        cur = collect_repo(current_cwd, args.session_start, gs, max_commits)
        cur["is_current"] = True
        repo_states.append(cur)

    scan_root: Path | None = None

    if args.no_multi_repo:
        # Fall back to current-repo-only, wrapped in the envelope.
        result = build_result(current_root, None, repo_states, multi_repo=False)
        sys.stdout.write(json.dumps(result, ensure_ascii=False) + "\n")
        return 0

    # Determine the candidate repos to read wide.
    candidates: list[str] = []

    if args.repos:
        # Explicit override — bypass discovery. Filter to actual git repos.
        for raw in args.repos.split(","):
            p = raw.strip()
            if not p:
                continue
            root = gs.is_git_repo(p)
            if root is None:
                warn(f"--repos entry is not a git repo, skipped: {p}")
                continue
            candidates.append(root)
    else:
        # Discovery — scan root = parent of current repo unless overridden.
        if args.repo_roots:
            scan_root = Path(args.repo_roots).expanduser()
        elif current_root is not None:
            scan_root = Path(current_root).parent
        else:
            scan_root = Path(current_cwd).parent
        if scan_root.is_dir():
            candidates = discover_repos(scan_root, gs)
        else:
            warn(f"scan root is not a directory: {scan_root}")

    # Read each candidate; include only those with ≥1 in-window commit.
    for root in candidates:
        state = collect_repo(root, args.session_start, gs, max_commits)
        key = _dedup_key(state)
        if key in seen:
            continue  # already the current repo, or a duplicate path
        if state.get("commits_in_window", 0) < 1:
            continue  # zero in-window commits → drop, keep output relevant
        seen.add(key)
        repo_states.append(state)

    result = build_result(current_root, scan_root, repo_states, multi_repo=True)
    sys.stdout.write(json.dumps(result, ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
