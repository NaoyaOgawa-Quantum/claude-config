# Encrypting Sensitive Repos with git-crypt

> **日本語版**: [git-crypt-guide.ja.md](git-crypt-guide.ja.md)
>
> **Related**: [sensitive-repo-patterns.md](sensitive-repo-patterns.md) — design patterns for repositories containing sensitive data (filename/commit message hygiene, bootstrap chain design, public-surface minimization). One layer above tool mechanics.

[git-crypt](https://github.com/AGWA/git-crypt) transparently encrypts files in a Git repository. Files are encrypted on push and decrypted on clone/pull, so you work with plaintext locally while GitHub stores ciphertext.

## Quick Start

### 1. Install

```bash
brew install git-crypt    # macOS
sudo apt install git-crypt # Debian/Ubuntu
```

### 2. Initialize in a repo

```bash
cd my-sensitive-repo
git-crypt init
```

This generates a symmetric key inside `.git/git-crypt/`. You need to export it for backup and sharing.

### 3. Export the key

```bash
mkdir -p ~/.secrets
git-crypt export-key ~/.secrets/git-crypt.key
chmod 600 ~/.secrets/git-crypt.key
```

> **Why `~/.secrets/`?** `setup.sh` auto-detects this path and unlocks encrypted repos automatically during bootstrap (Step 5b). If you use a different path, update `setup.sh` accordingly.

### 4. Configure `.gitattributes`

Create `.gitattributes` in the repo root to specify which files to encrypt:

```gitattributes
# Encrypt everything by default, whitelist exceptions
* filter=git-crypt diff=git-crypt

# Keep these unencrypted
CLAUDE.md !filter !diff
.gitignore !filter !diff
.gitattributes !filter !diff
```

Or encrypt specific directories only:

```gitattributes
# Encrypt only sensitive directories
data/** filter=git-crypt diff=git-crypt
private/** filter=git-crypt diff=git-crypt
SESSION.md filter=git-crypt diff=git-crypt
```

### 5. Commit and push

```bash
git add .gitattributes
git add .  # encrypted files are added normally
git commit -m "Initial commit (git-crypt encrypted)"
git push
```

Files matching the `.gitattributes` patterns are now encrypted on GitHub.

## CLAUDE.md Template

Add this near the top of your repo's `CLAUDE.md`:

```markdown
**⚠️ このリポは private 必須。<reason>を含むため、絶対に public にしないこと。**

**git-crypt 有効。** <files> が読めない場合 → `brew install git-crypt` → `git-crypt unlock ~/.secrets/git-crypt.key`
```

## Using One Key for Multiple Repos

You can reuse the same key across repos instead of generating a new one per repo:

```bash
cd another-repo
git-crypt init           # generates a new key (ignored)
git-crypt unlock ~/.secrets/git-crypt.key  # replaces with your shared key
```

**Trade-off**: Simpler key management, but one compromised key exposes all repos. Acceptable when all repos belong to the same owner and threat model.

## Setting Up on Another Machine

1. Transfer the key file securely (e.g., encrypted backup, direct copy via SSH)
2. Place it at `~/.secrets/git-crypt.key` with `chmod 600`
3. Run `setup.sh` — it auto-detects and unlocks all git-crypt repos

Or unlock manually:

```bash
cd my-sensitive-repo
git-crypt unlock ~/.secrets/git-crypt.key
```

## Key Backup

**The key file is the only way to decrypt your data.** If you lose it and don't have a backup, encrypted files on GitHub are unrecoverable.

Recommended practices:
- Store an encrypted backup in a separate location (cloud storage, USB drive, etc.)
- Use a strong passphrase for the backup encryption
- Test restoration periodically

## Troubleshooting

### Files appear as binary after clone

The repo is locked. Run `git-crypt unlock ~/.secrets/git-crypt.key`.

### `git-crypt: command not found` during git operations

The git filter uses an absolute path to `git-crypt`. Check `.git/config`:

```ini
[filter "git-crypt"]
    smudge = "git-crypt" smudge
    clean = "git-crypt" clean
    required = true
```

If the path is absolute (e.g., `/usr/local/Cellar/git-crypt/0.8.0/bin/git-crypt`), update it after reinstalling or upgrading git-crypt.

### `setup.sh` doesn't unlock my repos

Step 5b only runs when both conditions are met:
- `git-crypt` is installed
- `~/.secrets/git-crypt.key` exists

If either is missing, the step is silently skipped.
