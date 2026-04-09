# git-crypt で機密リポを暗号化する

> **English version**: [git-crypt-guide.md](git-crypt-guide.md)
>
> **関連**: [sensitive-repo-patterns.ja.md](sensitive-repo-patterns.ja.md) — git-crypt を使った機密リポの設計パターン集 (ファイル名・commit message・ブートストラップ経路・公開面の最小化など、ツールの使い方よりも一段上の運用設計)

[git-crypt](https://github.com/AGWA/git-crypt) は Git リポジトリ内のファイルを透過的に暗号化する。push 時に暗号化、clone/pull 時に復号されるため、ローカルでは平文で作業しつつ GitHub 上は暗号文で保存できる。

## クイックスタート

### 1. インストール

```bash
brew install git-crypt    # macOS
sudo apt install git-crypt # Debian/Ubuntu
```

### 2. リポで初期化

```bash
cd my-sensitive-repo
git-crypt init
```

対称鍵が `.git/git-crypt/` 内に生成される。バックアップと共有のためにエクスポートが必要。

### 3. 鍵のエクスポート

```bash
mkdir -p ~/.secrets
git-crypt export-key ~/.secrets/git-crypt.key
chmod 600 ~/.secrets/git-crypt.key
```

> **なぜ `~/.secrets/`？** `setup.sh` がこのパスを自動検出し、ブートストラップ時（Step 5b）に暗号化リポを自動 unlock する。別のパスを使う場合は `setup.sh` を更新すること。

### 4. `.gitattributes` の設定

リポルートに `.gitattributes` を作成し、暗号化対象を指定する：

```gitattributes
# デフォルトで全ファイル暗号化、例外をホワイトリスト
* filter=git-crypt diff=git-crypt

# これらは暗号化しない
CLAUDE.md !filter !diff
.gitignore !filter !diff
.gitattributes !filter !diff
```

または特定ディレクトリのみ暗号化：

```gitattributes
# 機密ディレクトリのみ暗号化
data/** filter=git-crypt diff=git-crypt
private/** filter=git-crypt diff=git-crypt
SESSION.md filter=git-crypt diff=git-crypt
```

### 5. コミット・push

```bash
git add .gitattributes
git add .  # 暗号化ファイルも通常通り add
git commit -m "Initial commit (git-crypt encrypted)"
git push
```

`.gitattributes` のパターンにマッチするファイルが GitHub 上で暗号化される。

## CLAUDE.md テンプレート

リポの `CLAUDE.md` 冒頭に以下を追加：

```markdown
**⚠️ このリポは private 必須。<理由>を含むため、絶対に public にしないこと。**

**git-crypt 有効。** <ファイル> が読めない場合 → `brew install git-crypt` → `git-crypt unlock ~/.secrets/git-crypt.key`
```

## 1つの鍵を複数リポで共有する

リポごとに新しい鍵を生成する代わりに、同じ鍵を使い回せる：

```bash
cd another-repo
git-crypt init           # 新しい鍵が生成される（無視される）
git-crypt unlock ~/.secrets/git-crypt.key  # 共有鍵で置き換え
```

**トレードオフ**: 鍵管理がシンプルになるが、1つの鍵が漏洩すると全リポが露出する。全リポが同一オーナーで脅威モデルが同じなら許容範囲。

## 別端末でのセットアップ

1. 鍵ファイルを安全に転送（暗号化バックアップ、SSH 経由の直接コピー等）
2. `~/.secrets/git-crypt.key` に配置し `chmod 600`
3. `setup.sh` を実行 — git-crypt リポを自動検出・unlock

手動 unlock も可能：

```bash
cd my-sensitive-repo
git-crypt unlock ~/.secrets/git-crypt.key
```

## 鍵のバックアップ

**鍵ファイルはデータを復号する唯一の手段。** 紛失してバックアップがなければ、GitHub 上の暗号化ファイルは復元不能。

推奨プラクティス：
- 暗号化したバックアップを別の場所に保管（クラウドストレージ、USB ドライブ等）
- バックアップの暗号化には強いパスフレーズを使用
- 定期的に復元テストを実施

## トラブルシューティング

### clone 後にファイルがバイナリ表示される

リポがロック状態。`git-crypt unlock ~/.secrets/git-crypt.key` を実行。

### git 操作中に `git-crypt: command not found`

git filter が `git-crypt` の絶対パスを使用している。`.git/config` を確認：

```ini
[filter "git-crypt"]
    smudge = "git-crypt" smudge
    clean = "git-crypt" clean
    required = true
```

パスが絶対パス（例: `/usr/local/Cellar/git-crypt/0.8.0/bin/git-crypt`）の場合、git-crypt の再インストールやアップグレード後に更新が必要。

### `setup.sh` がリポを unlock しない

Step 5b は以下の両方が揃った場合のみ実行される：
- `git-crypt` がインストール済み
- `~/.secrets/git-crypt.key` が存在する

どちらか一方でも欠けていればサイレントスキップされる。
