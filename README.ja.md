# claude-config

[Claude Code](https://docs.anthropic.com/en/docs/claude-code) で複数プロジェクトを一元管理するための共有規約・セットアップツール。

> **English version**: [README.md](README.md)

## なぜこのリポが必要か

Claude Code のコンテキストウィンドウは有限で、長い会話は圧縮（autocompact）される。構造化された復帰パスがなければ作業中の状態は失われる。プロジェクトが増えるほどこの問題は倍増し、手作業で規律を維持するのは現実的でない。

このリポは、正本として 1 つの規約 ([`CONVENTIONS.md`](CONVENTIONS.md)) をワークスペースへ symlink し、それを機械的に強制する hooks を備えることで、全プロジェクトに重複なく同じプロトコルを適用する。

## 具体例: autocompact 復帰

長いセッションのあと Claude Code は会話を圧縮する。構造化された復帰パスがなければ「今どこにいたか」が失われる。このセットアップでは:

1. `CLAUDE.md` は常にコンテキストに載っている。末尾の **How to Resume** が「SESSION.md を読め」と指示する。
2. `SESSION.md` に現在のタスク・進捗・未決事項がある（作業中は継続的に更新）。
3. Claude は説明し直さずに中断点から再開できる。

生命線は `SESSION.md` を陳腐化させないこと。`git push` 前の 4 軸レビュー（整合性・無矛盾性・効率性・安全性）がドリフトを出荷前に捕まえる — 実運用ではほぼ毎回何かが見つかる。

## クイックスタート

```bash
mkdir -p ~/Claude && cd ~/Claude
gh repo clone <your-username>/claude-config
cd claude-config && ./setup.sh
```

`setup.sh` は symlink・グローバル gitignore・Claude Code hooks とパーミッション・`post-merge` による自動同期・LaTeX pre-commit hooks・git-crypt 自動 unlock、macOS では PATH スナップショット修正と Hammerspoon 設定（オプション）までを一括で処理する。**全ステップの列挙と副作用の範囲**は [CLAUDE.md](CLAUDE.md) を参照。

Windows（MSYS/Cygwin）では symlink の代わりにファイルコピーを使い、`post-merge` hook が自動同期する。

## どこに何があるか

- **[CONVENTIONS.md](CONVENTIONS.md)** — 規約本体。何をどこに書くか、安全ガードレール、push プロトコル、情報書き先の判別表。
- **[CLAUDE.md](CLAUDE.md)** — このリポの運用ドキュメント: ディレクトリツリー、`setup.sh` の全手順、復帰方法。
- **[DESIGN.md](DESIGN.md)** — 規約がこの形になっている理由、設計判断、代替案、トレードオフ。
- **[conventions/](conventions/)** — ドメイン固有規約（LaTeX, MCP, 共有リポ, Substack, Scheduled Tasks, shell 環境, Dropbox refs, …）。各ファイルの冒頭に「いつロードするか」が書いてある。
- **[docs/](docs/)** — 運用 Tips, git-crypt ガイド, 機密リポ設計パターン, 規約設計の原則。[日本語 Tips](docs/usage-tips.ja.md) または [English tips](docs/usage-tips.md) から。
- **[hooks/](hooks/) と [scripts/](scripts/)** — 機械的強制: memory-guard, git-state-nudge, public-leak-guard, LaTeX Unicode 自動修正, 公開リポ監査。

## 核となるコンセプト

- **CLAUDE.md と SESSION.md** — CLAUDE.md は「このプロジェクトの作業方法」（更新稀）、SESSION.md は「今どこにいるか」（継続更新）。この分離が autocompact 復帰を確実なものにする。
- **情報の書き先** — すべての情報に正しい住所がある（メモリ / SESSION.md / CLAUDE.md / DESIGN.md / CONVENTIONS.md / 書かない）。表と論拠は [CONVENTIONS.md §2](CONVENTIONS.md)。`memory-guard` hooks がメモリディレクトリへの Edit/Write を機械的に検査する。
- **push 前 4 軸レビュー** — `git push` の前に整合性・無矛盾性・効率性・安全性をチェック。詳細は [CONVENTIONS.md §3](CONVENTIONS.md)。

## カスタマイズ

フォーク後、自分のワークフローに合わせて `CONVENTIONS.md` と `conventions/` を編集し、各マシンで `./setup.sh` を走らせる。

## ライセンス

MIT
