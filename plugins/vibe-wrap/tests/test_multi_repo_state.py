#!/usr/bin/env python3
"""
test_multi_repo_state.py — tests for vibe-wrap's multi-repo awareness (v0.2.0).

Covers the fix for first-soak finding #1 (single-repo blindness):

  1. Multi-repo git-state aggregation — two real temp git repos under a scan
     root are both discovered + reported, current-first.
  2. Discovery filtering — a repo with NO in-window commits is excluded; a
     non-git dir under the scan root is skipped.
  3. --repos override — an explicit repo set bypasses discovery.
  4. Read-wide / mutate-narrow boundary — only the current repo is flagged
     is_current; siblings carry their own state read-only.

Pure stdlib (unittest + subprocess + tempfile). Creates throwaway git repos
in a TemporaryDirectory; no network, no mutation of any real repo. Run with:

    python -m unittest discover -s plugins/vibe-wrap/tests -p "test_*.py"
    # or directly:
    python plugins/vibe-wrap/tests/test_multi_repo_state.py

Python 3.11+.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS_DIR = (
    Path(__file__).resolve().parent.parent / "skills" / "wrap" / "scripts"
)
MULTI_REPO_STATE = SCRIPTS_DIR / "multi-repo-state.py"
GIT_STATE = SCRIPTS_DIR / "git-state.py"

# An in-window session start: the test commits are made "now", so a window
# starting a year ago always includes them.
IN_WINDOW_START = "2000-01-01T00:00:00"


def _git(args: list[str], cwd: str) -> None:
    """Run a git command in cwd, raising on failure (test setup helper)."""
    subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )


def _init_repo(
    path: Path, *, with_commit: bool = True, commit_date: str | None = None
) -> None:
    """Create a git repo at `path`, optionally with one commit.

    `commit_date` backdates the commit (author + committer) so a `--since`
    filter can exclude it. Format: any git-accepted date, e.g. an ISO string.
    """
    path.mkdir(parents=True, exist_ok=True)
    _git(["init", "-b", "main"], str(path))
    _git(["config", "user.email", "test@example.com"], str(path))
    _git(["config", "user.name", "Test"], str(path))
    if with_commit:
        (path / "README.md").write_text("hello\n", encoding="utf-8")
        _git(["add", "README.md"], str(path))
        env = dict(os.environ)
        commit_args = ["commit", "-m", f"init {path.name}"]
        if commit_date:
            env["GIT_AUTHOR_DATE"] = commit_date
            env["GIT_COMMITTER_DATE"] = commit_date
            subprocess.run(
                ["git", *commit_args],
                cwd=str(path),
                check=True,
                capture_output=True,
                text=True,
                env=env,
            )
        else:
            _git(commit_args, str(path))


def _run_multi(args: list[str]) -> dict:
    """Run multi-repo-state.py with args, return parsed JSON stdout."""
    proc = subprocess.run(
        [sys.executable, str(MULTI_REPO_STATE), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert proc.returncode == 0, (
        f"multi-repo-state.py exited {proc.returncode}\n"
        f"stderr: {proc.stderr}"
    )
    return json.loads(proc.stdout)


@unittest.skipIf(shutil.which("git") is None, "git CLI not on PATH")
class MultiRepoStateTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        # Scan root holds sibling repos.
        self.scan_root = self.root / "projects"
        self.scan_root.mkdir()

    def tearDown(self) -> None:
        self._tmp.cleanup()

    # -- 1. Multi-repo aggregation ----------------------------------------

    def test_two_repos_both_discovered(self) -> None:
        """Two in-window repos under the scan root are both reported."""
        cur = self.scan_root / "repo-current"
        sib = self.scan_root / "repo-sibling"
        _init_repo(cur)
        _init_repo(sib)

        out = _run_multi(
            [
                "--session-start",
                IN_WINDOW_START,
                "--current-repo",
                str(cur),
                "--repo-roots",
                str(self.scan_root),
            ]
        )
        self.assertTrue(out["multi_repo"])
        labels = {r["repo_label"] for r in out["repos"]}
        self.assertIn("repo-current", labels)
        self.assertIn("repo-sibling", labels)
        # Per-repo state present: each carries its own commits.
        for r in out["repos"]:
            self.assertGreaterEqual(r["commits_in_window"], 1)
            self.assertEqual(r["is_repo"], True)

    def test_current_first_and_flagged(self) -> None:
        """The current repo is first and the only one flagged is_current."""
        cur = self.scan_root / "aaa-current"  # sorts first alphabetically too
        sib = self.scan_root / "zzz-sibling"
        _init_repo(cur)
        _init_repo(sib)
        # Give the sibling MORE commits so sort-by-count would put it first
        # if is_current ordering weren't winning.
        (sib / "extra.txt").write_text("x\n", encoding="utf-8")
        _git(["add", "extra.txt"], str(sib))
        _git(["commit", "-m", "second sib commit"], str(sib))

        out = _run_multi(
            [
                "--session-start",
                IN_WINDOW_START,
                "--current-repo",
                str(cur),
                "--repo-roots",
                str(self.scan_root),
            ]
        )
        self.assertEqual(out["repos"][0]["repo_label"], "aaa-current")
        self.assertTrue(out["repos"][0]["is_current"])
        current_flags = [r for r in out["repos"] if r["is_current"]]
        self.assertEqual(len(current_flags), 1, "exactly one current repo")

    # -- 2. Discovery filtering -------------------------------------------

    def test_repo_with_no_in_window_commits_excluded(self) -> None:
        """A sibling whose only commit predates the window is dropped."""
        cur = self.scan_root / "repo-current"
        stale = self.scan_root / "repo-stale"
        # Current repo commits "now" (in window). Stale repo's only commit is
        # backdated to 2010 — before a 2020 window start — so --since excludes
        # it. This mirrors the real soak: a session-start in the recent past,
        # siblings touched long ago are not part of this session.
        _init_repo(cur)
        _init_repo(stale, commit_date="2010-01-01T00:00:00")

        window_start = "2020-01-01T00:00:00"
        out = _run_multi(
            [
                "--session-start",
                window_start,
                "--current-repo",
                str(cur),
                "--repo-roots",
                str(self.scan_root),
            ]
        )
        labels = {r["repo_label"] for r in out["repos"]}
        self.assertIn("repo-current", labels, "current repo always kept")
        self.assertNotIn(
            "repo-stale", labels, "out-of-window sibling excluded"
        )

    def test_non_git_dir_skipped(self) -> None:
        """A plain (non-git) directory under the scan root is skipped."""
        cur = self.scan_root / "repo-current"
        plain = self.scan_root / "just-a-folder"
        _init_repo(cur)
        plain.mkdir()
        (plain / "notes.txt").write_text("not a repo\n", encoding="utf-8")

        out = _run_multi(
            [
                "--session-start",
                IN_WINDOW_START,
                "--current-repo",
                str(cur),
                "--repo-roots",
                str(self.scan_root),
            ]
        )
        labels = {r["repo_label"] for r in out["repos"]}
        self.assertNotIn("just-a-folder", labels)

    # -- 3. --repos override ----------------------------------------------

    def test_repos_override_bypasses_discovery(self) -> None:
        """An explicit --repos set is used; non-listed siblings are ignored."""
        cur = self.scan_root / "repo-current"
        listed = self.scan_root / "repo-listed"
        unlisted = self.scan_root / "repo-unlisted"
        _init_repo(cur)
        _init_repo(listed)
        _init_repo(unlisted)

        out = _run_multi(
            [
                "--session-start",
                IN_WINDOW_START,
                "--current-repo",
                str(cur),
                "--repos",
                str(listed),
            ]
        )
        labels = {r["repo_label"] for r in out["repos"]}
        self.assertIn("repo-current", labels, "current always included")
        self.assertIn("repo-listed", labels, "listed repo included")
        self.assertNotIn(
            "repo-unlisted",
            labels,
            "discovery bypassed — unlisted sibling not picked up",
        )

    def test_repos_override_skips_non_git_path(self) -> None:
        """A non-git path passed to --repos is skipped, not fatal."""
        cur = self.scan_root / "repo-current"
        plain = self.scan_root / "plain-dir"
        _init_repo(cur)
        plain.mkdir()

        out = _run_multi(
            [
                "--session-start",
                IN_WINDOW_START,
                "--current-repo",
                str(cur),
                "--repos",
                str(plain),
            ]
        )
        labels = {r["repo_label"] for r in out["repos"]}
        self.assertIn("repo-current", labels)
        self.assertNotIn("plain-dir", labels)

    # -- 4. --no-multi-repo fallback --------------------------------------

    def test_no_multi_repo_falls_back_to_current_only(self) -> None:
        """--no-multi-repo reports only the current repo, never siblings."""
        cur = self.scan_root / "repo-current"
        sib = self.scan_root / "repo-sibling"
        _init_repo(cur)
        _init_repo(sib)

        out = _run_multi(
            [
                "--session-start",
                IN_WINDOW_START,
                "--current-repo",
                str(cur),
                "--repo-roots",
                str(self.scan_root),
                "--no-multi-repo",
            ]
        )
        self.assertFalse(out["multi_repo"])
        labels = {r["repo_label"] for r in out["repos"]}
        self.assertEqual(labels, {"repo-current"})

    # -- 5. Commit cap (bounded output) -----------------------------------

    def test_max_commits_caps_shown_but_counts_truth(self) -> None:
        """--max-commits caps the shown list; commits_in_window stays true."""
        cur = self.scan_root / "repo-current"
        _init_repo(cur)  # 1 commit
        for i in range(5):
            f = cur / f"f{i}.txt"
            f.write_text(f"{i}\n", encoding="utf-8")
            _git(["add", f.name], str(cur))
            _git(["commit", "-m", f"commit {i}"], str(cur))
        # 6 total commits now.

        out = _run_multi(
            [
                "--session-start",
                IN_WINDOW_START,
                "--current-repo",
                str(cur),
                "--repo-roots",
                str(self.scan_root),
                "--max-commits",
                "3",
            ]
        )
        repo = out["repos"][0]
        self.assertEqual(repo["commits_in_window"], 6)
        self.assertEqual(len(repo["commits"]), 3)
        self.assertTrue(repo["commits_truncated"])


@unittest.skipIf(shutil.which("git") is None, "git CLI not on PATH")
class GitStateSingleRepoStillWorks(unittest.TestCase):
    """The existing single-repo entry point must keep working unchanged."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name) / "solo"
        _init_repo(self.repo)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_git_state_repo_flag_via_repo_arg(self) -> None:
        """git-state.py --repo <path> reports is_repo=True with commits."""
        proc = subprocess.run(
            [
                sys.executable,
                str(GIT_STATE),
                "--repo",
                str(self.repo),
                "--session-start",
                IN_WINDOW_START,
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        state = json.loads(proc.stdout)
        self.assertTrue(state["is_repo"])
        self.assertGreaterEqual(len(state["commits"]), 1)
        self.assertEqual(state["branch_name"], "main")

    def test_git_state_non_git_dir(self) -> None:
        """git-state.py against a non-git dir returns the empty shape."""
        plain = Path(self._tmp.name) / "plain"
        plain.mkdir()
        proc = subprocess.run(
            [sys.executable, str(GIT_STATE), "--repo", str(plain)],
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        state = json.loads(proc.stdout)
        self.assertFalse(state["is_repo"])
        self.assertIsNone(state["repo_root"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
