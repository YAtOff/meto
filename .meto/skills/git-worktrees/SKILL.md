---
name: git-worktrees
description: Use git worktrees for isolated parallel development on multiple branches
---

# Git Worktrees Skill

You are an expert at using git worktrees for isolated parallel development.

## Overview

Git worktrees create isolated workspaces sharing the same repository, allowing work on multiple branches simultaneously without switching.

**Core principle:** Systematic directory selection + safety verification = reliable isolation.

**Announce at start:** "I'm using the git-worktrees skill to set up an isolated workspace."

## Directory Selection

If the project is at folder `<project>`, the worktrees are at `.<project>.worktrees/`

Example: `/Users/me/myproject/` → worktrees at `myproject.worktrees/`

## Safety Verification

For project-local directories (`.worktrees` or `worktrees`):
- Verify directory exists before creating worktree
- Ensure no conflicts with existing worktrees

## Creation Steps

### 1. Detect Project Name

```bash
project=$(basename "$(git rev-parse --show-toplevel)")
path="../$project.worktrees/$BRANCH_NAME"
```

### 2. Create Worktree

```bash
git worktree add "$path" -b "$BRANCH_NAME"
cd "$path"
```

### 3. Run Project Setup

Auto-detect and run from project files:
- `package.json` → `npm install` or `yarn` or `pnpm install`
- `requirements.txt` or `pyproject.toml` → `uv sync` or `pip install`
- `Cargo.toml` → `cargo fetch`
- `go.mod` → `go mod download`

### 4. Verify Clean Baseline

Run tests to ensure worktree starts clean.

**If tests fail:** Report failures, ask whether to proceed or investigate.

**If tests pass:** Report ready.

### 5. Report Location

Provide full path to the new worktree.

## Common Mistakes

**Proceeding with failing tests**
- Problem: Can't distinguish new bugs from pre-existing issues
- Fix: Report failures, get explicit permission to proceed

**Hardcoding setup commands**
- Problem: Breaks on projects using different tools
- Fix: Auto-detect from project files (package.json, etc.)

## Example Workflow

```
You: I'm using the git-worktrees skill to set up an isolated workspace.

[Check .myproject.worktrees/ - exists]
[Create worktree: git worktree add ../myproject.worktrees/auth -b feature/auth]
[Run npm install]
[Run npm test - 47 passing]

Worktree ready at /Users/me/myproject/.worktrees/auth
Tests passing (47 tests, 0 failures)
Ready to implement auth feature
```

## Red Flags

**Never:**
- Skip baseline test verification
- Proceed with failing tests without asking

**Always:**
- Auto-detect and run project setup
- Verify clean test baseline
- Use `.<project>.worktrees/` pattern for project-local worktrees
