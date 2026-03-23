# claude-config

## 概要
`~/Claude` 共通設定ファイルを管理する設定リポ。どの端末でも clone + setup.sh で同じ規約が適用される。

## リポジトリ情報
- パス: `~/Claude/claude-config/`
- ブランチ: `main`
- リモート: `NaoyaOgawa-Quantum/claude-config` (public, GitHub)

## 構造
```
claude-config/
├── CLAUDE.md        # このファイル（リポ固有の指示書）
├── CONVENTIONS.md   # 全リポ共通規約（正本）
├── README.md        # プロジェクト説明（英語/日本語）
├── setup.sh         # symlink セットアップスクリプト
├── gfm-rules.md     # GFM CJK bold 対策リファレンス
├── LICENSE          # MIT
└── .gitignore
```

## セットアップ（新しい端末で）
```bash
mkdir -p ~/Claude && cd ~/Claude
gh repo clone NaoyaOgawa-Quantum/claude-config
cd claude-config && ./setup.sh
```

setup.sh が自動で行うこと:
1. `~/Claude/CONVENTIONS.md` → `claude-config/CONVENTIONS.md` の相対 symlink 作成
2. `NaoyaOgawa-Quantum` の全リポを `~/Claude/` 以下に clone（未取得のもののみ）

## How to Resume
1. このリポには SESSION.md は不要（永続的な設定リポのため）
2. 作業内容は CONVENTIONS.md と README.md の変更
3. 変更後は commit + push（全リモートに）

## 関連リポ
- `NaoyaOgawa-Quantum/zenn-articles` — Zenn.dev 日本語記事（このリポについての記事もそちらに格納）
- `NaoyaOgawa-Quantum/devto-articles` — 英語記事ソース（投稿先: dev.to）

## 安全規則（公開リポ）
**このリポは public。** 以下を絶対にコミットしない:
- 実名（GitHub ユーザー名 `NaoyaOgawa-Quantum` は可）
- メールアドレス
- 非公開リポ名
- 金融データ・口座情報
- 所属機関名
- 他ユーザーのユーザー名

変更前に「公開リポに載せて問題ないか」を必ず確認すること。

## 運用ルール
- CONVENTIONS.md の正本はこのリポ内のファイル
- `~/Claude/CONVENTIONS.md` は symlink（setup.sh が作成）
- CONVENTIONS.md を変更したらこのリポで commit + push
- 他端末では `git pull` で同期

## 自動更新ルール（必須）
以下を人間に言われなくても自動で行う:
- CONVENTIONS.md を変更したら → このリポで commit + push
- CLAUDE.md のルールの詳細は `~/Claude/CONVENTIONS.md` 参照
