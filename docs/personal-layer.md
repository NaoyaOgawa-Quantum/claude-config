# Personal Layer — odakin's four-layer architecture

> **日本語版**: 同じファイル内で日本語セクションを併記しています。

## What is the personal layer?

Claude Code conventions live in **four layers**, numbered by **audience size** (largest to smallest):

| # | Layer | Example | Audience | Depends on |
|---|---|---|---|---|
| 1 | Common conventions | this `claude-config` repo | public / shared | — |
| 2 | Shared project layer | a private repo you share with collaborators (e.g. an admin or research repo) | the project's collaborator set | layer 1 only |
| 3 | **Personal layer** | `<base>/<your>-prefs/` (a private repo or local dir of your own) | only you | layers 1, 2 |
| 4 | Volatile memory | `~/.claude/.../memory/MEMORY.md` | local | any |

The numbering follows audience containment: `public ⊃ collaborator set ⊃ owner ⊃ machine-local`, so a smaller layer number always means a wider audience. This makes the dependency rule directional and intuitive — a layer can only depend on layers with **smaller or equal** numbers.

> **History note**: as of **2026-05-01** the numbering was changed to align with audience size (layers 2 and 3 were swapped — old `2 = personal / 3 = shared` became new `2 = shared / 3 = personal`). Commit messages and docs from before that date may use the old numbering; if you see "layer 2 = personal layer" in older commit logs, that's the old scheme. See `claude-config/DESIGN.md §「4 層モデルの renumber: layer 2 ↔ 3 swap (2026-05-01)」` for the rationale and full impact map.

**Core rule**: each layer may only depend on layers whose audience contains its own. So a shared-project layer (layer 2) can reference claude-config (layer 1, public) but **must not** reference your personal layer (layer 3, only you), because your collaborators cannot see your personal layer.

## When should you create a personal layer?

You should create one when you start having:
- preferences that span multiple projects (writing style, identity blocks, signature lines)
- a list of repos you maintain
- per-machine secret paths (e.g. where you keep git-crypt keys for shared projects)
- personal workflow rules you want Claude to remember automatically

If you only ever work in one repo and have nothing to share between projects, you don't need a personal layer at all. claude-config alone is enough.

## Layout

A personal layer is a **directory** (typically a private git repo, but a local-only directory works) containing:

```
<your>-prefs/
├── .claude-personal-layer        # marker file (zero bytes) — claude-config setup.sh detects this
├── CLAUDE.md                     # the personal home instruction file (~/Claude/CLAUDE.md symlinks here)
├── repos.md                      # your repo list (optional, replaces having it in MEMORY.md)
├── shared-project-keys.md        # mapping of shared-project repo names → local key paths (optional)
├── user-profile.md               # identity, signatures, account info (optional)
├── dropbox-collabs.yaml          # Dropbox shared-PDF registry (optional, see conventions/dropbox-refs.md)
└── ...                           # other personal rule files
```

When the personal layer contains `dropbox-collabs.yaml`, `claude-config/setup.sh` automatically:
1. runs `scripts/setup-dropbox-refs.sh` to create per-repo `dropbox-refs/` symlinks pointing into your Dropbox install
2. installs a `post-merge` git hook in the personal layer so subsequent `git pull` regenerates the symlinks

See [`conventions/dropbox-refs.md`](../conventions/dropbox-refs.md) for the schema and full details.

The **marker file** `.claude-personal-layer` is the canonical signal that this directory is a personal layer. claude-config's `setup.sh` looks for it under `~/Claude/*/` (or whichever base directory you use) and, if it finds exactly one match, links `~/Claude/CLAUDE.md` to that directory's `CLAUDE.md`.

## Creating your own personal layer

1. Make a directory next to claude-config:
   ```bash
   mkdir -p ~/Claude/my-prefs
   cd ~/Claude/my-prefs
   touch .claude-personal-layer
   ```
2. Optionally make it a private git repo:
   ```bash
   git init
   gh repo create my-prefs --private --source=. --push
   ```
3. Copy the templates from `claude-config/templates/personal-layer/` and fill them in (see [templates README](../templates/personal-layer/README.md)).
4. Re-run `claude-config/setup.sh` so the symlink at `~/Claude/CLAUDE.md` is updated to point at your new layer.

## Multiple personal layers? Override?

If `setup.sh` finds **more than one** directory with the marker, it errors out and asks you to disambiguate via the `CLAUDE_PERSONAL_LAYER` environment variable:

```bash
CLAUDE_PERSONAL_LAYER=~/Claude/work-prefs ./setup.sh
```

To opt out entirely (e.g. on a shared machine), use:

```bash
CLAUDE_PERSONAL_LAYER=none ./setup.sh
```

## Shared-project key mapping

If you participate in shared-project layers that use git-crypt with shared keys (one common pattern: the key file lives in a Dropbox folder shared with the team, each team member places it at their preferred local path), put the local paths in `shared-project-keys.md`:

```markdown
# Shared Project Key Paths

| Project    | Local key path                  |
|------------|---------------------------------|
| my-project | ~/.secrets/my-project.key       |
```

Claude reads this file via the personal-layer cascade and uses the right path automatically when entering a shared-project repo. Without this file, Claude falls back to the convention path `~/.secrets/<project-name>.key`.

## FAQ

**Q. Is the personal layer required?**
No. claude-config works without one. The default `~/Claude/CLAUDE.md` from `templates/root-CLAUDE.md.default` is installed instead.

**Q. Should the personal layer be a git repo?**
Recommended for cross-machine sync, but a local-only directory is fine. Both work with the marker-file detection.

**Q. Can other people see my personal layer?**
Only if you make it a public repo. Default: keep it private (or local-only). Personal layers typically contain identity info, signatures, repo lists, and per-machine paths — not state secrets, but still personal.

**Q. How do I migrate from an existing setup that hard-coded a specific dir name?**
Just create the marker file in your existing dir: `touch ~/Claude/<your-dir>/.claude-personal-layer`. Re-run `setup.sh`. The detection picks it up regardless of the directory name.
