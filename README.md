# claude-config

Shared conventions and bootstrap tooling for managing multiple projects with [Claude Code](https://docs.anthropic.com/en/docs/claude-code).

> **Japanese version**: [README.ja.md](README.ja.md)

## Why this exists

Claude Code's context window is finite. Long sessions get compressed (autocompact), and without a structured recovery path, in-flight state is lost. Across many projects the problem multiplies: each one needs the same discipline, but maintaining it by hand drifts fast.

This repo solves that with a single authoritative set of rules ([`CONVENTIONS.md`](CONVENTIONS.md)), symlinked into your workspace, plus hooks that enforce the rules mechanically. Every project follows the same protocol without duplication.

## Example: autocompact recovery

After a long session Claude Code compresses the conversation. Without a recovery path, the assistant loses "where we were." With this setup:

1. `CLAUDE.md` is always in context. Its **How to Resume** section says "read SESSION.md."
2. `SESSION.md` holds the current task, progress, and open decisions — updated continuously during work.
3. Claude picks up exactly where it left off, no re-explanation needed.

The critical habit is keeping `SESSION.md` honest. A 4-axis push-before-check protocol (consistency, non-contradiction, efficiency, safety) catches drift before it ships — in practice it finds something almost every time.

## Quick start

```bash
mkdir -p ~/Claude && cd ~/Claude
gh repo clone <your-username>/claude-config
cd claude-config && ./setup.sh
```

`setup.sh` handles symlinks, global gitignore, Claude Code hooks and permissions, a `post-merge` hook for auto-sync, LaTeX pre-commit hooks, git-crypt auto-unlock, and (on macOS) a PATH snapshot fix plus optional Hammerspoon config. **Full step list and exactly what it touches**: [CLAUDE.md](CLAUDE.md).

On Windows (MSYS/Cygwin) symlinks are replaced with file copies and the `post-merge` hook keeps them in sync.

## What's where

- **[CONVENTIONS.md](CONVENTIONS.md)** — the rule set. Where to write what, safety guardrails, push protocol, information-destination table.
- **[CLAUDE.md](CLAUDE.md)** — this project's ops doc: directory tree, full `setup.sh` step list, how to resume.
- **[DESIGN.md](DESIGN.md)** — why the rules are shaped this way; design decisions, alternatives, trade-offs.
- **[conventions/](conventions/)** — domain-specific rules (LaTeX, MCP, shared repos, Substack, scheduled tasks, shell env, Dropbox refs, …). Each file's header states when to load it.
- **[docs/](docs/)** — usage tips, git-crypt guide, sensitive-repo patterns, convention design principles. Start with [English tips](docs/usage-tips.md) or [Japanese tips](docs/usage-tips.ja.md).
- **[hooks/](hooks/) and [scripts/](scripts/)** — mechanical enforcement: memory-guard, git-state-nudge, public-leak-guard, LaTeX Unicode auto-fix, public-repo audit.

## Core concepts

- **CLAUDE.md vs SESSION.md** — CLAUDE.md is "how to work on this project" (rarely updated). SESSION.md is "where we are right now" (continuously updated). This separation is what makes autocompact recovery reliable.
- **Information destinations** — every piece of information has one correct home (memory / SESSION.md / CLAUDE.md / DESIGN.md / CONVENTIONS.md / don't-write-it). Table and rationale in [CONVENTIONS.md §2](CONVENTIONS.md). The `memory-guard` hooks enforce it on Edit/Write into the memory directory.
- **Push-before-check** — a 4-axis review (consistency, non-contradiction, efficiency, safety) before every `git push`. Detail in [CONVENTIONS.md §3](CONVENTIONS.md).

## Context budget

claude-config itself ships a near-empty auto-load: the default `<base>/CLAUDE.md` is ~25 lines and `CONVENTIONS.md` is reached via pointer, costing tokens only when Claude actually reads it. Out of the box, claude-config adds almost nothing to Claude Code's session-start context.

Once you add a personal layer or sub-project `CLAUDE.md`s, watch the **combined auto-load size** — Claude Code auto-loads every `CLAUDE.md` from the working directory up the tree, so layers accumulate.

Rough targets (from [`docs/convention-design-principles.md`](docs/convention-design-principles.md) §10.7):

- **200K-context model** (autocompact fires ≈ 167K): keep the combined auto-load under ~50 KB to keep autocompact rare during long sessions.
- **1M-context model**: the same target is effectively free, but the chain-load discipline still keeps session startup snappy.

If autocompact fires more than you expect, check per-file byte density (§10.7) and the sub-project `CLAUDE.md` chain (§10.10–10.11) before cutting actual content.

## For English-speaking users

The rule text in `CONVENTIONS.md` and most files under `conventions/` is written in Japanese, but the structure is language-agnostic. Fork the repo and translate or replace the rule text to match your workflow — `setup.sh` uses `gh auth` to detect your GitHub user and works as-is. READMEs, the git-crypt guide, and most script comments are bilingual.

## Customization

Fork, edit `CONVENTIONS.md` and the files under `conventions/` to match your workflow, and run `./setup.sh` on each machine.

## License

MIT
