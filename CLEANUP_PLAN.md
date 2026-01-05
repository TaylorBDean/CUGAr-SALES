# Cleanup Plan: Duplicate PRs & Stale Branches

**Last Updated:** 2025-12-31  
**Purpose:** Comprehensive guide for reconciling duplicate pull requests and removing stale branches from the cugar-agent repository.

---

## Table of Contents

1. [Overview](#overview)
2. [Duplicate PR Reconciliation](#duplicate-pr-reconciliation)
3. [Stale Branch Cleanup](#stale-branch-cleanup)
4. [Verification & Rollback](#verification--rollback)
5. [Automation & Prevention](#automation--prevention)

---

## Overview

This cleanup plan addresses technical debt related to:
- **Duplicate Pull Requests:** Multiple PRs targeting the same feature or fix
- **Stale Branches:** Local/remote branches no longer in active development
- **Orphaned Commits:** Work committed to branches that were never merged

### Benefits
- ✅ Reduced repository clutter
- ✅ Clearer development history
- ✅ Easier navigation of active work
- ✅ Reduced merge conflicts
- ✅ Improved CI/CD pipeline efficiency

---

## Duplicate PR Reconciliation

### 1. Identify Duplicate PRs

#### Steps:
1. Visit the **Pull Requests** tab in the repository
2. Filter by status: **Open** and **Draft**
3. Look for PRs with:
   - Similar titles or descriptions
   - Changes to the same files
   - Same target branch (usually `main` or `develop`)
   - Creation dates close to each other

#### Using GitHub CLI:
```bash
gh pr list --repo TylrDn/cugar-agent --state all --limit 100 | grep -i "duplicate\|wip\|draft"
```

#### Using Git:
```bash
git log --all --oneline --graph --decorate | head -50
```

### 2. Audit Duplicate PR Contents

For each duplicate PR pair:

```bash
# Check out each PR branch locally
git fetch origin pull/<PR_NUMBER>/head:pr-<PR_NUMBER>
git checkout pr-<PR_NUMBER>

# Review commits
git log --oneline <TARGET_BRANCH>..<PR_BRANCH>

# View file changes
git diff <TARGET_BRANCH>..<PR_BRANCH> --name-only
```

**Document:**
- [ ] Which PR has the most recent/correct changes?
- [ ] Are there differences in code quality or completeness?
- [ ] Which PR has better documentation/tests?
- [ ] Are all commits from both PRs necessary?

### 3. Merge Strategy

Choose one of the following approaches:

#### Option A: Keep One, Close the Other (Recommended for Minor Changes)
1. Identify the superior PR (more complete, better tested, cleaner history)
2. In the inferior PR:
   - Add a comment: `This is a duplicate of #<SUPERIOR_PR>. Closing in favor of that PR.`
   - Close the PR without merging
3. Delete the associated branch:
   ```bash
   git push origin --delete <inferior-branch>
   ```

#### Option B: Squash and Merge (For Complex Changes)
1. Review both PRs for valuable commits
2. Manually cherry-pick useful commits from the duplicate PR
3. Add them to the main PR in a logical order
4. Close the duplicate PR after verification

#### Option C: Combine Changes (For Partially Overlapping PRs)
1. Create a new branch from the superior PR branch:
   ```bash
   git checkout <superior-branch>
   git pull origin <superior-branch>
   git checkout -b combined/<feature-name>
   ```
2. Cherry-pick unique commits from the duplicate PR:
   ```bash
   git cherry-pick <commit-hash>
   ```
3. Resolve any conflicts
4. Force-push to combined branch and create new PR
5. Close both original PRs

### 4. Close & Cleanup Duplicate PRs

**For Each Duplicate PR to Close:**

1. Verify all valuable changes are preserved elsewhere
2. Post a closing comment with rationale:
   ```markdown
   Closing this PR in favor of #<KEPT_PR_NUMBER>.
   
   Changes from this PR have been preserved in: #<KEPT_PR_NUMBER>
   
   This cleanup is part of repository maintenance to reduce duplicate efforts.
   ```
3. Click "Close Pull Request" (do not merge)
4. Delete the associated branch:
   ```bash
   gh pr delete <PR_NUMBER> --repo TylrDn/cugar-agent
   # Or manually:
   git push origin --delete <branch-name>
   ```

### 5. Reconciliation Checklist

- [ ] All duplicate PRs identified and documented
- [ ] File changes compared and verified
- [ ] Decision made for each duplicate pair
- [ ] Superior PRs updated with any beneficial changes
- [ ] Duplicate PRs closed with explanatory comments
- [ ] Associated branches deleted
- [ ] Team notified of changes
- [ ] CI/CD checks passing on remaining PRs

---

## Stale Branch Cleanup

### 1. Identify Stale Branches

#### Criteria for "Stale":
- No commits in the last **30 days** (configurable)
- Not the default branch (`main`, `develop`, `master`)
- Not associated with an open PR
- Not tagged as a release or stable version

#### Using Git (Local):
```bash
# List branches not updated in the last 30 days
git for-each-ref --sort=-committerdate refs/heads --format='%(refname:short) %(committerdate:short)' | \
  awk '{print $1, $2}' | \
  while read branch date; do
    days_old=$(( ($(date +%s) - $(date -d "$date" +%s)) / 86400 ))
    if [ $days_old -gt 30 ]; then
      echo "$branch (${days_old} days old)"
    fi
  done
```

#### Using GitHub CLI:
```bash
# List all branches
gh api repos/TylrDn/cugar-agent/branches --paginate | \
  jq -r '.[] | select(.commit.author.date | fromdateiso8601 | . < now - (30*24*3600)) | .name'
```

#### Manual Inspection:
1. Visit repository **Branches** page
2. Sort by "Last Commit"
3. Note branches with dates older than 30 days
4. Filter out protected branches and release branches

### 2. Audit Stale Branches

For each stale branch, determine:

```bash
# Check if branch is merged into main
git merge-base --is-ancestor <branch-name> main && echo "Merged" || echo "Not merged"

# View unmerged commits
git log main..<branch-name> --oneline

# Check associated PR status
gh pr list --repo TylrDn/cugar-agent --state all --head <branch-name>

# View last commit details
git log -1 --format="%H %ai %s" <branch-name>
```

**Document:**
- [ ] Is the branch merged into main?
- [ ] Does it have an associated open PR?
- [ ] What was the purpose of this branch?
- [ ] Should any changes be preserved?

### 3. Branch Deletion Strategy

#### Category 1: Merged & Safe to Delete
```bash
# Verify merged
git branch --merged main | grep <branch-name>

# Delete locally
git branch -d <branch-name>

# Delete remotely
git push origin --delete <branch-name>
```

#### Category 2: Unmerged but Obsolete
```bash
# If truly no value:
git branch -D <branch-name>
git push origin --delete <branch-name>

# Document the deletion reason
echo "Deleted: <branch-name> - Reason: obsolete/abandoned" >> CLEANUP_LOG.md
```

#### Category 3: Unmerged with Valuable Changes
```bash
# Create a summary commit
git log main..<branch-name> --oneline > /tmp/<branch-name>_commits.txt

# Decide: merge, cherry-pick, or archive
# Option 1: Merge (if appropriate)
git checkout main
git merge --no-ff <branch-name>

# Option 2: Cherry-pick specific commits
git cherry-pick <commit-hash>

# Option 3: Create an archive branch (if historical value)
git branch archive/<branch-name> <branch-name>
git push origin archive/<branch-name>
git push origin --delete <branch-name>
```

### 4. Automated Cleanup Script

Create a `cleanup_branches.sh` script:

```bash
#!/bin/bash
# cleanup_branches.sh - Remove stale branches from cugar-agent

REPO="TylrDn/cugar-agent"
DAYS_THRESHOLD=30
PROTECTED_BRANCHES=("main" "develop" "master" "production")

echo "🧹 Starting stale branch cleanup..."
echo "Repository: $REPO"
echo "Threshold: $DAYS_THRESHOLD days"
echo "---"

# Fetch latest
git fetch origin

# Find and delete stale branches
git for-each-ref --sort=-committerdate refs/remotes/origin --format='%(refname:short) %(committerdate:short)' | \
  while read full_ref ref_date; do
    branch="${full_ref#origin/}"
    
    # Skip protected branches
    if [[ " ${PROTECTED_BRANCHES[@]} " =~ " ${branch} " ]]; then
      continue
    fi
    
    # Check age
    days_old=$(( ($(date +%s) - $(date -d "$ref_date" +%s)) / 86400 ))
    
    if [ $days_old -gt $DAYS_THRESHOLD ]; then
      # Check if merged
      if git merge-base --is-ancestor "origin/$branch" origin/main; then
        echo "🗑️  Deleting merged branch: $branch (${days_old} days old)"
        git push origin --delete "$branch" 2>/dev/null || echo "❌ Failed to delete $branch"
      else
        echo "⚠️  Unmerged branch (skipped): $branch (${days_old} days old)"
        echo "   Review this branch manually for valuable changes"
      fi
    fi
  done

echo "---"
echo "✅ Cleanup complete!"
```

**Usage:**
```bash
chmod +x cleanup_branches.sh
./cleanup_branches.sh
```

### 5. Stale Branch Cleanup Checklist

- [ ] All stale branches identified
- [ ] Audit completed for each branch
- [ ] Decision made (merge, delete, archive)
- [ ] Valuable commits preserved
- [ ] Branches deleted from remote
- [ ] Local references cleaned (`git prune`)
- [ ] Team notified of deletions
- [ ] CI/CD pipeline still healthy

---

## Verification & Rollback

### Post-Cleanup Verification

```bash
# Verify branch count reduced
git branch -r | wc -l

# Verify main branch integrity
git log main --oneline | head -20

# Check for orphaned commits
git fsck --lost-found

# Verify all important commits are reachable
git log --all --oneline | grep <keyword>
```

### Rollback Procedure

If cleanup causes issues:

1. **Recover Deleted Branch (within 30 days):**
   ```bash
   # Check reflog
   git reflog show origin/<branch-name>
   
   # Restore
   git checkout -b <branch-name> <commit-hash>
   git push origin <branch-name>
   ```

2. **Review GitHub's Reflog:**
   - Visit repository Settings → Danger Zone
   - Check "Recent deletions" if available
   - Some hosting platforms retain deletion history

3. **Contact Maintainers:**
   - If branches were deleted in error, notify team immediately
   - Provide commit hashes for recovery

---

## Automation & Prevention

### 1. GitHub Actions Workflow

Create `.github/workflows/branch-cleanup.yml`:

```yaml
name: Monthly Branch Cleanup

on:
  schedule:
    - cron: '0 0 1 * *'  # First day of each month
  workflow_dispatch:  # Manual trigger

jobs:
  cleanup:
    runs-on: ubuntu-latest
    permissions:
      contents: write
    steps:
      - uses: actions/checkout@v3
        with:
          fetch-depth: 0
      
      - name: Configure Git
        run: |
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git config user.name "github-actions[bot]"
      
      - name: Delete merged branches
        run: |
          git fetch origin
          for branch in $(git branch -r --merged origin/main | grep -v main | sed 's|origin/||'); do
            git push origin --delete "$branch" || true
          done
      
      - name: Create cleanup report
        run: |
          echo "# Branch Cleanup Report" >> $GITHUB_STEP_SUMMARY
          echo "Run: $(date)" >> $GITHUB_STEP_SUMMARY
          echo "Deleted merged branches older than 30 days" >> $GITHUB_STEP_SUMMARY
```

### 2. Branch Protection Rules

Prevent accidental deletion:

1. Go to Settings → Branches
2. Add branch protection for `main` and `develop`:
   - ✅ Require a PR before merging
   - ✅ Require status checks to pass
   - ✅ Dismiss stale PR approvals
   - ✅ Require branches to be up to date before merging

### 3. PR Policies

Add to repository contributing guidelines:

```markdown
## Branch Naming Conventions

- Feature branches: `feature/<feature-name>`
- Bug fix branches: `bugfix/<issue-number>-<description>`
- Release branches: `release/<version>`
- Hotfix branches: `hotfix/<issue-number>`

## PR Guidelines

- Create one PR per feature/bug
- Link related issues with `Closes #<issue>`
- Delete branch after merging
- Do not create duplicate PRs; coordinate with team instead
```

### 4. Monitoring

Set up notifications for:
- Old, inactive branches
- Stale draft PRs
- Duplicate PR detection

---

## Maintenance Schedule

| Task | Frequency | Owner |
|------|-----------|-------|
| Identify stale branches | Weekly | Automated |
| Review duplicate PRs | As needed | PR reviewer |
| Execute branch cleanup | Monthly | Maintainer |
| Verify repository health | Monthly | Maintainer |
| Update this plan | Quarterly | Team |

---

## Contact & Support

For questions about this cleanup plan:
- **Repository:** TylrDn/cugar-agent
- **Issue Tracker:** Use the GitHub Issues page
- **Discussions:** Use the Discussions feature

---

## Changelog

| Date | Change | Author |
|------|--------|--------|
| 2025-12-31 | Initial cleanup plan created | TylrDn |

---

**Remember:** Always verify changes before executing cleanup operations. When in doubt, ask the team!
