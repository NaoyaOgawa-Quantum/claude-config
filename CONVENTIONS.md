# ~/Claude リポジトリ規約

最終更新: 2026-03-18

---

## 1. リポジトリ作成・同期

```bash
# 新規作成
cd ~/Claude
gh repo create odakin/<name> --private --description "<English description>" --clone
cd <name> && git branch -M main
# 必須ファイル作成（§2参照）→ initial commit + push
git add . && git commit -m "Initial commit: <概要>" && git push -u origin main

# 未clone リポの同期
gh repo list odakin --limit 50 --json name  # 一覧取得
gh repo clone odakin/<name>                  # clone
```

- **リポの description（`--description`）は必ず英語で書く。** dev.to 等の embed カードに表示されるため。

リポ一覧の正本は **MEMORY.md の「リポ一覧（正本）」セクション**。新規作成・clone 後は必ず追記。**新しいリポを作る前に、既存リポで対応できないか MEMORY.md のリポ一覧を確認すること。**

---

## 2. 必須ファイル

| ファイル | 役割 |
|---------|------|
| `CLAUDE.md` | 永続的指示書（構造・実行方法・復帰手順）。構造変更時のみ更新 |
| `SESSION.md` | 揮発的作業ログ（現在状態・タスク進捗・次のステップ）。作業の進行に応じて自動更新 |
| `.gitignore` | ビルド成果物・OS/エディタファイル・機密情報の除外 |

原則: CLAUDE.md は「どうやるか」、SESSION.md は「今どこにいるか」。

---

## 3. 自動更新プロトコル

**人間に言われなくても自動で行う。**

### SESSION.md 更新タイミング

- タスク完了時 → `[x]` にし成果物を記録
- 重要な判断時 → 「直近の決定事項」に記録
- ファイル作成/大幅変更時 → パスと概要を記録
- エラー・ブロッカー発生時 → 問題と状態を記録
- 長い作業の区切り → 中間状態を記録（autocompact 対策）
- 外部公開・デプロイ時 → 日時・コミット・内容を記録

### CLAUDE.md 更新タイミング

リポ構造変更、実行手順確定、Phase 大幅進行時のみ。

### push 前チェック

```
1. SESSION.md が実態と一致しているか確認・更新
2. CLAUDE.md の更新が必要か判断（構造変更があった場合のみ）
3. CLAUDE.md を更新した場合 → CONVENTIONS.md と矛盾がないか確認
4. 冗長・陳腐化・曖昧な記述がないか確認
5. commit → push
```

軽微な変更（typo 等）で CLAUDE.md に影響がなければステップ 2-4 はスキップ可。

### SESSION.md 更新時の整合性確認

- 直前の議論と矛盾がないか
- コード/出力と記述が一致しているか
- 古い情報が残留していないか

SESSION.md は autocompact 後の唯一の復帰情報。不正確な記述は致命的。

### autocompact 復帰フロー

CLAUDE.md 自動読み込み → "How to Resume" → SESSION.md 読む → 作業継続

---

## 4. CLAUDE.md テンプレート

```markdown
# <プロジェクト名>

## 概要
<1-2文>

## リポジトリ情報
- パス: `~/Claude/<name>/`
- ブランチ: `main`
- リモート: `odakin/<name>` (private)

## 構造
\`\`\`
<tree>
\`\`\`

## 実行環境
- 言語 / 依存 / 実行コマンド

## How to Resume
1. SESSION.md を読む → 現在状態と次のステップを把握
2. 「次のステップ」に従って作業継続
3. 不明点はユーザーに確認

## 自動更新ルール（必須）
- タスク完了時 → SESSION.md 更新
- 重要な判断時 → SESSION.md に記録
- push 前 → SESSION.md/CLAUDE.md が実態と一致か確認
- 詳細は `~/Claude/CONVENTIONS.md` §3 参照
```

共有リポでは CONVENTIONS.md §3 の内容を CLAUDE.md 内に直接記述すること。

---

## 5. SESSION.md テンプレート

```markdown
# <プロジェクト名> Session

## 現在の状態
**作業中**: <今やっていること>

### タスク進捗
- [x] <完了タスク>
- [ ] <進行中> ← **ここから再開**

## 次のステップ
1. <次のアクション>

## 直近の決定事項
- <日付>: <内容>

## 作業ログ
### <日付>
- <何をしたか>
```

「現在の状態」と「次のステップ」は常に最上部。作業ログは下に追記。

---

## 6. .gitignore

`~/.gitignore_global` で TeX 中間ファイル・.DS_Store をグローバル除外済み。
ローカル専用リポはプロジェクト固有のみでOK。**共有リポ** では共同編集者のために全パターンを含める。

標準パターン: 共通（.DS_Store, .claude/, *~, *.swp）、Python（__pycache__/, .venv/）、LaTeX（*.aux, *.bbl 等）、Mathematica（*.mx）、Node（node_modules/）

---

## 7. ディレクトリ命名

`src/`（ソース）、`docs/`（参考資料）、`referee/`（レフェリーレポート）、`analyses/`（解析）、`tools/`（ユーティリティ）、`scripts/`（自動化）

---

## 8. Git 規約

- ブランチ `main` 統一。コミットメッセージは英語・動詞始まり
- コミット後は常に push（push 前チェック §3 を挟む）。**複数リモートがあるリポでは全リモートに push する**（`git remote -v` で確認）
- セッション終了時は未コミット変更があれば必ず commit + push
- ファイル名にバージョン番号をつけない（git が管理）

---

## 9. 安全規則（絶対厳守）

1. 自分が作っていないファイル/ディレクトリの削除前に `ls` で確認しユーザーに提示
2. 既存データ削除時はリネーム (`mv old old.bak`) を優先提案
3. force push 禁止（必要なら `--force-with-lease`）
4. 機密情報（.env, credentials, 個人情報）はコミットしない
5. 同じファイルを複数リポに置かない（正本を1つ）
6. 破壊的操作（リポ削除・ブランチ削除・reset --hard 等）は必ず事前にユーザー確認
7. 自分（odakin）のリポのみ操作。他ユーザーのリポは絶対に触らない
8. **LaTeX の式（equation/align 環境内）は原則として変更しない。** 変更が必要な場合は必ず事前にユーザーに確認し、承認を得てから行うこと。英語校正・文法修正など確実に正しい本文修正は可。物理的内容を含む文の追加・書き換えはコメントとして提案し、本文への直接挿入は避ける — ハルシネーションが本文に紛れ込むと著者のチェック負担が極めて大きいため

---

## 10. 網羅性の検証

「全部」「全て」を主張する場合、列挙の**前に**機械的な検証基準（grep 件数、テスト総数など）を定め、列挙**後に**照合する。検証基準が定義できない場合は「全部」と主張しない。

---

## 11. その他

- **画像出力**: ファイル名は内容を反映。生成後は `open` で表示
- **GFM ルール**: 日本語 bold 対策の詳細は `~/Claude/claude-config/gfm-rules.md` 参照
