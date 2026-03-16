# claude-config

## 概要
`~/Claude` 共通設定ファイルを管理する設定リポ。どの端末でも clone + setup.sh で同じ規約が適用される。

## リポジトリ情報
- パス: `~/Claude/claude-config/`
- ブランチ: `main`
- リモート: `odakin/claude-config` (private, GitHub)

## 構造
```
claude-config/
├── CLAUDE.md        # このファイル
├── CONVENTIONS.md   # 全リポ共通規約（正本）
├── setup.sh         # symlink セットアップスクリプト
└── .gitignore
```

## セットアップ（新しい端末で）
```bash
mkdir -p ~/Claude && cd ~/Claude
gh repo clone odakin/claude-config
cd claude-config && ./setup.sh
```

setup.sh が自動で行うこと:
1. `~/Claude/CONVENTIONS.md` → `claude-config/CONVENTIONS.md` の相対 symlink 作成
2. `odakin` の全リポを `~/Claude/` 以下に clone（未取得のもののみ）

## 運用ルール
- CONVENTIONS.md の正本はこのリポ内のファイル
- `~/Claude/CONVENTIONS.md` は symlink（setup.sh が作成）
- CONVENTIONS.md を変更したらこのリポで commit + push
- 他端末では `git pull` で同期

## 自動更新ルール（必須）
以下を人間に言われなくても自動で行う:
- CONVENTIONS.md を変更したら → このリポで commit + push
- CLAUDE.md のルールの詳細は `~/Claude/CONVENTIONS.md` 参照
