# Repository Cleanup Execution Guide

This document provides step-by-step instructions for executing a comprehensive cleanup of the cugar-agent repository. Follow these steps carefully to ensure a clean, maintainable codebase.

**Last Updated:** 2025-12-31

---

## Overview

This cleanup process includes:
- Closing duplicate pull requests
- Deleting stale branches
- Verifying CI/CD pipeline status
- Documenting changes and resolutions

---

## Prerequisites

Before starting the cleanup, ensure you have:
- Write access to the TylrDn/cugar-agent repository
- GitHub CLI installed and authenticated (`gh --version`)
- Git installed and configured locally
- Access to the CI/CD dashboard/logs

---

## Step 1: Identify Duplicate Pull Requests

### 1.1 List All Open Pull Requests
```bash
gh pr list --repo TylrDn/cugar-agent --state open
```

### 1.2 Review for Duplicates
- Look for PRs with similar titles or descriptions
- Check for PRs addressing the same issue
- Identify PRs with overlapping code changes
- Document PR numbers that are duplicates

### 1.3 Create a Cleanup Log
Create a file `CLEANUP_LOG.txt` to track all actions:
```
Date: 2025-12-31
Action: Duplicate PR Cleanup

PR #XXX - Duplicate of PR #YYY - Status: [CLOSED/KEPT]
PR #AAA - Duplicate of PR #BBB - Status: [CLOSED/KEPT]
```

---

## Step 2: Close Duplicate Pull Requests

### 2.1 For Each Duplicate PR

**Step 2.1.1:** View PR details
```bash
gh pr view <PR_NUMBER> --repo TylrDn/cugar-agent
```

**Step 2.1.2:** Add a closing comment
```bash
gh pr comment <PR_NUMBER> --repo TylrDn/cugar-agent \
  --body "This PR is a duplicate of #<PRIMARY_PR_NUMBER>. Closing in favor of the primary PR. All changes and discussions should continue there."
```

**Step 2.1.3:** Close the PR
```bash
gh pr close <PR_NUMBER> --repo TylrDn/cugar-agent
```

**Step 2.1.4:** Log the action
```
PR #<PR_NUMBER> - Closed as duplicate of PR #<PRIMARY_PR_NUMBER>
```

### 2.2 Verify Closures
```bash
gh pr list --repo TylrDn/cugar-agent --state closed --limit 10
```

---

## Step 3: Identify and Delete Stale Branches

### 3.1 List All Branches
```bash
git fetch --prune
git branch -a
```

### 3.2 Identify Stale Branches

Look for branches that meet these criteria:
- Last commit is older than 30 days
- Associated PR has been merged or closed
- No active development work

**Check branch age:**
```bash
git for-each-ref --sort=-committerdate --format='%(committerdate:short) %(refname:short)' refs/remotes/origin/
```

### 3.3 Create a List of Stale Branches

Document branches to delete:
```
Stale Branch: feature/old-feature-1
  Last commit: 2025-09-30
  Associated PR: #123 (Merged)
  
Stale Branch: hotfix/old-fix
  Last commit: 2025-08-15
  Associated PR: #145 (Closed)
```

---

## Step 4: Delete Stale Branches

### 4.1 For Each Stale Branch

**Step 4.1.1:** Verify branch association
```bash
gh pr list --repo TylrDn/cugar-agent --state all --search "branch:<BRANCH_NAME>"
```

**Step 4.1.2:** Delete the remote branch
```bash
gh api repos/TylrDn/cugar-agent/git/refs/heads/<BRANCH_NAME> -X DELETE
```

Or using Git:
```bash
git push origin --delete <BRANCH_NAME>
```

**Step 4.1.3:** Delete local branch (if applicable)
```bash
git branch -d <BRANCH_NAME>
```

**Step 4.1.4:** Log the action
```
Deleted branch: <BRANCH_NAME> (Last commit: YYYY-MM-DD)
```

### 4.2 Verify Deletions
```bash
git fetch --prune
git branch -a | grep -v "origin/main\|origin/develop\|origin/master"
```

---

## Step 5: Verify CI/CD Pipeline Status

### 5.1 Check Recent Workflow Runs
```bash
gh run list --repo TylrDn/cugar-agent --limit 10
```

### 5.2 View Latest Workflow Status
```bash
gh run list --repo TylrDn/cugar-agent --status completed --limit 1
```

### 5.3 Inspect Failed Workflows (if any)
```bash
gh run list --repo TylrDn/cugar-agent --status failure --limit 5
```

### 5.4 Check Workflow Details
```bash
gh run view <RUN_ID> --repo TylrDn/cugar-agent
```

### 5.5 Verify CI/CD Configuration

**Step 5.5.1:** Check GitHub Actions workflows
```bash
ls -la .github/workflows/
```

**Step 5.5.2:** Validate workflow syntax
- Review `.github/workflows/*.yml` files
- Ensure all required secrets and variables are configured
- Verify branch protection rules are in place

**Step 5.5.3:** Confirm Status Checks
- Navigate to Settings → Branches → Branch protection rules
- Verify required status checks are enabled for `main` branch
- Confirm all CI/CD checks are passing

### 5.6 Log CI/CD Status
```
CI/CD Verification - 2025-12-31
✓ All GitHub Actions workflows present
✓ Latest workflow run: [STATUS]
✓ No critical failures detected
✓ Branch protection rules enforced
```

---

## Step 6: Final Verification and Reporting

### 6.1 Run Final Checks
```bash
# Verify branch cleanup
git fetch --prune
git branch -a | wc -l

# Verify PR closure
gh pr list --repo TylrDn/cugar-agent --state open

# Run any existing tests locally (if applicable)
npm test
# or
python -m pytest
```

### 6.2 Create a Cleanup Summary

Document the cleanup execution:

**File: CLEANUP_SUMMARY.md**
```markdown
# Repository Cleanup Summary - 2025-12-31

## Duplicate PRs Closed
- PR #XXX: [Description] → Closed as duplicate of #YYY
- PR #AAA: [Description] → Closed as duplicate of #BBB
**Total: X PRs closed**

## Stale Branches Deleted
- feature/old-feature-1 (Last commit: 2025-09-30)
- hotfix/old-fix (Last commit: 2025-08-15)
**Total: X branches deleted**

## CI/CD Verification
- ✓ GitHub Actions workflows operational
- ✓ Latest run: [STATUS] - [DATE TIME]
- ✓ No blocking issues detected
- ✓ Branch protection rules active

## Cleanup Completed By
- User: TylrDn
- Date: 2025-12-31 11:25:05 UTC
```

### 6.3 Push Summary to Repository
```bash
git add CLEANUP_SUMMARY.md CLEANUP_LOG.txt
git commit -m "docs: Add repository cleanup execution summary for 2025-12-31"
git push origin main
```

---

## Step 7: Post-Cleanup Verification

### 7.1 Verify Repository Health
- [ ] All open PRs are legitimate and active
- [ ] No stale branches remain
- [ ] CI/CD pipeline is fully operational
- [ ] Branch protection rules are enforced
- [ ] No merge conflicts on main branch

### 7.2 Team Communication
- [ ] Notify team of cleanup completion
- [ ] Share cleanup summary
- [ ] Document any decisions made (e.g., which PR was kept for duplicates)
- [ ] Provide access to cleanup logs

### 7.3 Update Documentation
- [ ] Update main README if needed
- [ ] Archive old documentation (if applicable)
- [ ] Update contribution guidelines if changed

---

## Rollback Procedures

If something goes wrong during cleanup:

### Restore a Deleted Branch
```bash
# Find the commit SHA from git reflog or GitHub
git reflog
git checkout -b <BRANCH_NAME> <COMMIT_SHA>
git push origin <BRANCH_NAME>
```

### Reopen a Closed PR
- Navigate to the PR on GitHub
- Click "Reopen pull request"
- Add a comment explaining why it was reopened

### Restore Branch Protection Rules
- Check GitHub repository settings history (if available)
- Manually reconfigure branch protection rules in Settings → Branches

---

## Troubleshooting

### Issue: Cannot delete branch (protected)
**Solution:** 
1. Go to Settings → Branches
2. Remove or modify branch protection rules for that branch
3. Delete the branch
4. Re-enable protection rules

### Issue: PR requires rebasing after stale branch deletion
**Solution:**
```bash
git fetch
git rebase origin/main
git push --force-with-lease
```

### Issue: CI/CD workflow failures after cleanup
**Solution:**
1. Check the specific workflow run logs: `gh run view <RUN_ID> --log`
2. Verify no dependencies on deleted branches
3. Manually trigger a new workflow run: `gh workflow run <WORKFLOW_FILE>`

---

## Checklist for Completion

- [ ] Duplicate PRs identified and documented
- [ ] All duplicate PRs closed with comments
- [ ] Stale branches identified and documented
- [ ] All stale branches deleted locally and remotely
- [ ] CI/CD pipeline verified and operational
- [ ] Cleanup summary document created
- [ ] Summary pushed to main branch
- [ ] Team notified of cleanup completion
- [ ] Cleanup logs archived (optional but recommended)

---

## Additional Resources

- [GitHub CLI Documentation](https://cli.github.com/manual/)
- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Git Branch Management](https://git-scm.com/book/en/v2/Git-Branching-Branch-Management)
- [Repository Settings](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features)

---

**For questions or issues during cleanup, contact the repository maintainers.**
