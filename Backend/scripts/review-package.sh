#!/usr/bin/env bash
# review-package.sh — emit the stage diff for the swe-reviewer subagent.
#
# Purpose: feed the reviewer ONLY what changed (brief + diff), never the whole repo.
# This is the context-minimization rule borrowed from superpowers
# (see ORCHESTRATION.md "Budget rule" and NOTES.md 2026-06-19). Dev-only; never shipped.
#
# Usage:
#   bash scripts/review-package.sh              # uncommitted working-tree changes vs HEAD
#   bash scripts/review-package.sh BASE HEAD    # diff between two committed refs/tags
#
# Output (stdout): a stat summary, the list of changed files, then the unified diff.
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

if [ "$#" -ge 2 ]; then
  BASE="$1"; HEAD="$2"
  RANGE="${BASE}..${HEAD}"
  echo "=== review-package: ${RANGE} ==="
  echo "--- changed files ---"
  git diff --stat "${BASE}" "${HEAD}"
  echo "--- diff ---"
  git diff "${BASE}" "${HEAD}"
else
  echo "=== review-package: working tree vs HEAD (incl. untracked) ==="
  echo "--- changed files ---"
  git status --short
  echo "--- tracked diff ---"
  git diff HEAD
  # include untracked files so brand-new stage files (e.g. tests/, new modules) are reviewed
  echo "--- untracked files ---"
  git ls-files --others --exclude-standard
fi
