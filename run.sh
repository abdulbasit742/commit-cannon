#!/usr/bin/env bash
# commit-cannon runner
# Builds the commit chain LOCALLY (no network per commit), then pushes once.
set -euo pipefail

COUNT="${1:-1000000}"        # how many commits this batch
REMOTE="${2:-origin}"
BRANCH="master"

echo ">> generating $COUNT commits via fast-import..."
time python3 generate.py "$COUNT" | git fast-import --force --quiet

echo ">> repacking aggressively..."
git repack -adq --depth=50 --window=50

echo ">> pushing $BRANCH (one shot)..."
git push "$REMOTE" "$BRANCH" --force

echo ">> done. total commits:"
git rev-list --count "$BRANCH"
