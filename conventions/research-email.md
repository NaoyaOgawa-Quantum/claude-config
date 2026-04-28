# 研究メール規約

研究共同研究のメール通信を管理するリポで適用。CLAUDE.md から参照: `~/Claude/claude-config/conventions/research-email.md`

## メール分類

受信メールを以下の基準で分類する:

| 分類 | 条件 | 処理先 |
|------|------|--------|
| 研究メール | 送信者が `research-collab/collaborators.yaml` に登録 **または** 件名が既知プロジェクトに関連 | `research-collab/threads/{project}.yaml` |
| 事務メール | 大学事務・委員会・人事・学生対応 | `email-office/TODO.yaml` |
| その他 | 上記以外 | 通常対応（必要に応じて分類） |

## スレッド記録ルール

### 記録するもの
- 共同研究者との往復メール
- 論文投稿・レフェリーレポート関連
- 学会招待・講演依頼（研究関連）
- 研究に関する議論・質問

### 記録しないもの
- 一方的な通知メール（ML配信、学会ニュース等）
- スパム・広告

### スレッド記録の書式

```yaml
- thread_id: "Gmail thread ID"    # gmail_read_thread で再取得可能
  subject: "件名"
  participants: [collaborator_id]  # collaborators.yaml の id
  account: lab | cis | personal   # どの Gmail アカウントか
  started: YYYY-MM-DD
  last_message: YYYY-MM-DD
  status: active | waiting | resolved
  summary: |
    スレッドの要約（数行）
  action_items:
    - description: "アクション内容"
      assignee: odakin | collaborator_id
      status: pending | done | waiting
      due: YYYY-MM-DD | null
      completed: YYYY-MM-DD | null
```

### status の使い分け
- **active**: やり取りが進行中
- **waiting**: 相手の返信待ち
- **resolved**: 議論終了、アクション完了

## セッション開始時の手順

プロジェクトリポで作業開始する際:
1. `research-collab/threads/{project}.yaml` を読む
2. status が active/waiting のスレッドを報告
3. 未完了の action_items を報告
4. Gmail MCP で新着メールをチェック（共同研究者からのもの）

## メール送信後の記録

Claude がメールを送信（またはドラフト作成）した場合、**同じセッション内で即時に**以下を実行:
1. 該当スレッドの `last_message` を更新
2. `summary` に送信内容の要約を追記
3. 関連する action_items の status を更新

「次のセッションでやる」は禁止。送信と記録は原子的操作。

## 研究者連絡先 (email) の取得手順

新規研究者にコンタクトする際、メールアドレスが手元になければ以下の優先順位で探す:

1. **collaborators.yaml / 既存リポの `researchers.yaml` 等の手元 DB** — 過去に登録があれば最速
2. **論文 PDF の 1 ページ目 (arXiv 等)** ← **推奨**。著者所属の脚注として email が記載されている case が多く、確実に取得できる
   - `WebFetch` で `https://arxiv.org/pdf/<arxiv-id>` を取って著者 email を抽出
   - 学会誌掲載済の論文も最初の正式版 PDF に email がある
3. **所属機関の公式メンバーページ** — 例: 大学研究室の member 一覧。**ただし mask されていることが多い** (`****@univ.example` 等)
4. **OpenReview / Semantic Scholar / Google Scholar の著者プロフィール** — mask されていることが多く、確実に取得できないことが多い
5. **共著者・知人経由の問い合わせ** — 上記で見つからない場合の最後の手段

### 失敗例 (反パターン)

メンバーページの mask された表示を見て「公開で取得できない」と user に尋ねたが、論文 PDF を直接見ればすぐ取れた case があった。**arXiv 論文がある相手なら、まず PDF を見る**。

### 注意

- メールアドレスは PII。**取得経路 (= どこで見つけたか) を log に残す** (= researchers.yaml の notes に source を書く) と、後日「このアドレスは公開情報か?」を判定できる
- 公開ページに載っていない address を間接ルート (= 紹介・名刺) で取得した場合は、そのことも notes に記録 (= 受信者から「どこで知ったか」と聞かれた場合の説明責任)
