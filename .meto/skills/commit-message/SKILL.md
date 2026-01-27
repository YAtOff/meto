---
name: commit-message
description: Generate conventional commit messages following best practices
---

# Commit Message Skill

You are an expert at writing clear, informative git commit messages.

## Format

Follow Conventional Commits specification:
- `type(scope): subject`
- Types: feat, fix, docs, refactor, test, chore, style, perf, ci, build
- Subject: imperative mood, no period, max 50 chars
- Body (optional): explain why, not what, wrap at 72 chars

## Examples

Good commit messages:
- `feat(auth): add OAuth2 login flow`
- `fix(api): handle null response in user endpoint`
- `docs(readme): update installation instructions`
- `refactor(parser): simplify token extraction logic`
- `test(auth): add integration tests for login`

Bad commit messages:
- `fixed stuff` (too vague, no type)
- `Added new feature for users to login with OAuth` (too long, not imperative)
- `Fix bug.` (has period, no scope)

## Analysis Steps

1. Review git diff to understand changes
2. Identify primary purpose (new feature, bug fix, refactor, etc.)
3. Identify scope (module/component affected)
4. Write concise subject line in imperative mood
5. Add body if context needed (why this change was made)

## Tips

- Focus on **why** the change was made, not **what** changed (code shows what)
- Use imperative mood: "add" not "added" or "adds"
- Keep subject under 50 chars for GitHub/GitLab UI readability
- Separate subject from body with blank line
- Use body to explain motivation, context, and trade-offs
