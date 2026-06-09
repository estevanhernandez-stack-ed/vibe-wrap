#!/usr/bin/env python3
"""
test_git_state_encoding.py — regression test for the git-state UTF-8 fix.

Covers evolve-wrap 2026-06-09 finding #1 (mojibake in git-sourced wrap-doc
lines): `git-state.py`'s `run_git()` called `subprocess.run(..., text=True)`
with no `encoding=`, so on Windows git's UTF-8 output decoded as cp1252 and an
em-dash in a commit subject rendered as `â€"`. The fix adds
`encoding="utf-8", errors="replace"`, matching every other subprocess call
site in the plugin.

This test commits a subject containing an em-dash (U+2014) and asserts
git-state.py round-trips it intact — no cp1252 mojibake. The bug only
reproduces under a cp1252 default locale (Windows), but the assertion holds on
every platform, so it's a valid cross-platform regression guard.

Pure stdlib (unittest + subprocess + tempfile). Creates a throwaway git repo
in a TemporaryDirectory; no network, no mutation of any real repo. Run with:

    python -m unittest discover -s plugins/vibe-wrap/tests -p "test_*.py"
    # or:
    python -m pytest plugins/vibe-wrap/tests/test_git_state_encoding.py

Python 3.11+.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS_DIR = (
    Path(__file__).resolve().parent.parent / "skills" / "wrap" / "scripts"
)
GIT_STATE = SCRIPTS_DIR / "git-state.py"

# A window starting in 2000 always includes a commit made "now".
IN_WINDOW_START = "2000-01-01T00:00:00"

EM_DASH = "—"  # —
# The cp1252 mis-decode of a UTF-8 em-dash (bytes E2 80 94) — the symptom the
# fix prevents: E2->â (U+00E2), 80->€ (U+20AC), 94->” (U+201D).
MOJIBAKE = "â€”"  # â€”
# Mirrors the real failing line from the 2026-05-23 doc (the vibe-insights
# "R4 polish" subject), trimmed to the em-dash that broke.
EM_DASH_SUBJECT = f"docs(insights){EM_DASH}R4 polish"


def _git(args: list[str], cwd: str) -> None:
    """Run a git command in cwd, raising on failure (test setup helper)."""
    subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


@unittest.skipIf(shutil.which("git") is None, "git CLI not on PATH")
class GitStateEncodingTests(unittest.TestCase):
    """git-state.py must decode git output as UTF-8 (regression: finding #1)."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name) / "repo"
        self.repo.mkdir(parents=True)
        _git(["init", "-b", "main"], str(self.repo))
        _git(["config", "user.email", "test@example.com"], str(self.repo))
        _git(["config", "user.name", "Test"], str(self.repo))
        (self.repo / "README.md").write_text("hello\n", encoding="utf-8")
        _git(["add", "README.md"], str(self.repo))
        _git(["commit", "-m", EM_DASH_SUBJECT], str(self.repo))

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _run_git_state(self) -> dict:
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
        return json.loads(proc.stdout)

    def test_em_dash_subject_round_trips(self) -> None:
        """A commit subject with an em-dash survives intact — no mojibake."""
        state = self._run_git_state()
        subjects = [c["subject"] for c in state["commits"]]
        self.assertIn(
            EM_DASH_SUBJECT,
            subjects,
            f"em-dash subject not found intact; got {subjects!r}",
        )

    def test_no_cp1252_mojibake_in_subjects(self) -> None:
        """The cp1252 mis-decode (â€”) must never appear in any subject."""
        state = self._run_git_state()
        for subject in (c["subject"] for c in state["commits"]):
            self.assertNotIn(
                MOJIBAKE,
                subject,
                "cp1252 mojibake present — git-state.py lost its UTF-8 decode",
            )
            self.assertNotIn(
                "â", subject, "stray cp1252 byte (â) in commit subject"
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
