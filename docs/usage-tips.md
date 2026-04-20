# Usage Tips

Practical patterns discovered through real-world use across 20+ projects with [claude-config](../README.md).

> **日本語版**: [usage-tips.ja.md](usage-tips.ja.md)

## 1. Start every session fresh

Don't continue long conversations. Start a new session each time and say "resume project X." Claude reads CLAUDE.md, then SESSION.md, and picks up where you left off. This eliminates autocompact risk entirely.

**Prerequisite:** SESSION.md must be up to date. The auto-update protocol (CONVENTIONS.md §3) handles this.

## 2. The pre-push incantation

Before every push, say:

> "Check consistency, non-contradiction, and efficiency. Push."

Claude will cross-check your documentation against reality. In practice, **this catches something almost every time**: stale counts, circular references, duplicate headings, outdated status fields.

For public repos, add "safety":

> "Check consistency, non-contradiction, efficiency, and safety. Push."

Claude will grep for PII, private repo names, email addresses, and other sensitive data.

## 3. Say "think deeply" for non-trivial decisions

Claude defaults to quick answers. Explicitly asking it to think deeply yields trade-off analysis, alternative evaluation, and edge case consideration. Use this for architecture decisions, feature prioritization, and UI/UX choices — anywhere the answer isn't obvious.

## 4. Record the WHY, not just the WHAT

When you decide to implement (or not implement) a feature, record the reasoning in SESSION.md:

```markdown
# Bad
- "Don't implement X filter"

# Good
- "Don't implement X filter (2026-03-21) — data source is
  secondary (parser estimate, 97.1% coverage), no alternative
  for the ~290 unparseable entries, and no harm in not filtering"
```

Include the date. Circumstances change; dateless decisions look like permanent laws.

## 5. Use competitive analysis for feature planning

Ask Claude to fetch a competitor's site and analyze: "What are we losing to this site?" Then critically evaluate each gap — often, what looks like a weakness is already covered by existing features, or isn't worth implementing.

## 6. Invest feedback in conventions and hooks, not memory

When Claude makes a recurring mistake, the intuitive fix is to save a feedback memory (`~/.claude/` memory system). **Don't.** This repo's `memory-guard.sh` hook actively denies feedback-style writes to the memory directory, because memory behaves as precedent-as-training-data: the same entry that's supposed to correct behavior gets re-loaded each session and reinforces the pattern more than it corrects it. Full reasoning: [`convention-design-principles.md`](convention-design-principles.md) §8.3.

Write durable corrections where they survive across machines and sessions:

- **A canonical rule belongs in [CONVENTIONS.md](../CONVENTIONS.md) or `conventions/*.md`** — git-synced, loaded every session, editable, and pointed to from CLAUDE.md. This is the place for "always do X" / "never do Y" rules that generalize.
- **A catastrophic-risk mistake (data loss, secret leak, unrecoverable external action) belongs in a hook** — PreToolUse `deny`, pre-commit block, or permission allowlist. §8.2 ranks the intervention strengths; §8.4 explains why mechanical enforcement is structurally stronger than any written rule.
- **An annoyance-level mistake (four keystrokes to correct in-session) belongs in no artifact at all** — accept the correction and move on. §9.1 triage. Reaching for memory here is usually an anxiety response, not an engineering decision (§8.5).

The original observation still holds: a correction-only record makes Claude overly cautious. When an unusual approach *worked*, write *that* into the same canonical convention alongside the "don't" rules. The balance between corrections and validated patterns lives in the convention file — not in memory, where the load-and-repeat loop would amplify whichever side is denser.

## 7. Single source of truth, no circular references

Pick exactly one place for each piece of information. Reference it from other places, but never duplicate the content. Always specify the section name, not just the file:

```markdown
# Bad — circular reference
CONVENTIONS.md: "Repo list is in MEMORY.md"
MEMORY.md: "Repo list is in CONVENTIONS.md §1"

# Good — single source with precise pointer
CONVENTIONS.md: "Repo list: see MEMORY.md, section 'Repo Index'"
MEMORY.md → [actual repo table lives here]
```

## 8. Mind the CLAUDE.md chain in sub-projects

Claude Code auto-loads every `CLAUDE.md` from your current working directory up the tree. Working in `~/Claude/repo/sub/` loads `~/Claude/CLAUDE.md`, `~/Claude/repo/CLAUDE.md`, and `~/Claude/repo/sub/CLAUDE.md` all at once. This matters more on the 200K-context model, where autocompact fires around 167K tokens — a bloated chain eats headroom before your session even starts.

Keep each layer to its own role:

- **Top-level `~/Claude/CLAUDE.md`** — identity, global rules, repo index.
- **Repo `CLAUDE.md`** — repo overview, how to run things, pointers to details.
- **Sub-project `CLAUDE.md`** — commands, quirks, an architecture super-summary of 5–8 one-line items with pointers to `docs/architecture.md`. Target ~80–100 lines.

Heavy narrative, parameter tables, and design rationale live in `docs/` (not auto-loaded) and are referenced by pointer. Principles and worked examples in [`convention-design-principles.md`](convention-design-principles.md) §10.10–10.11.
