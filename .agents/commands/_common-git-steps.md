Standard git operations used across review/implement commands.

### Current branch
```bash
git branch --show-current
```

### Commit range (diff base vs HEAD)
```bash
# PR mode: diff against PR base
MERGE_BASE=$(gh pr view "$PR_NUMBER" --json baseRefName --jq '.baseRefName' 2>/dev/null || echo "main")
BASE_SHA=$(git merge-base "$MERGE_BASE" HEAD)
echo "$BASE_SHA...HEAD"

# Branch mode: diff against merge-base with main
BASE_SHA=$(git merge-base main HEAD)
echo "$BASE_SHA...HEAD"
```

### Files changed in scope
```bash
git diff "$BASE_SHA"...HEAD --name-only
```

### Staleness check
```bash
CURRENT_HEAD=$(git rev-parse HEAD)
if [ "$REVIEW_HEAD" != "$CURRENT_HEAD" ]; then
  echo "HEAD has moved since review"
  git log --oneline "$REVIEW_HEAD..$CURRENT_HEAD"
fi
```
