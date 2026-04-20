# 運用Tips

[claude-config](../README.ja.md) を使った20以上のプロジェクトの実運用で見つけた実践パターン。

> **English version**: [usage-tips.md](usage-tips.md)

## 1. 毎回新規セッションで「〜を再開」

長い会話を続けない。毎回新しいセッションを立ち上げて「〇〇プロジェクトを再開」と言う。Claude が CLAUDE.md → SESSION.md を読んで、前回の続きから作業を再開する。autocompact のリスクがゼロになる。

**前提:** SESSION.md が常に最新であること（CONVENTIONS.md §3 の自動更新プロトコルが必須）。

## 2. push 前の呪文

push の前に毎回こう言う:

> 「整合性、無矛盾性、効率性をチェック。プッシュ。」

Claude がドキュメントとコードの齟齬を見つけて直す。 **ほぼ毎回何か見つかる**: 古い件数、循環参照、見出し重複、ステータスの陳腐化など。

public リポでは「安全性」を追加:

> 「整合性、無矛盾性、効率性、安全性をチェック。プッシュ。」

個人情報・非公開リポ名・メールアドレス等の漏洩を grep でチェックしてくれる。

## 3. 「深く検討して」で浅い回答を防ぐ

Claude はデフォルトでさっさと答える。「深く検討して」と言うと、トレードオフ分析・代替案の比較・エッジケースの考慮が出てくる。正解が1つでない判断（設計、機能の要否、UIの配置など）で使う。

## 4. 決定事項の WHY を日付付きで記録

機能の採用/不採用を決めたら、 **理由を含めて** SESSION.md に記録する:

```markdown
# 悪い例
- 「現在営業中」フィルターは実装しない

# 良い例
- 「現在営業中」フィルターは実装しない（2026-03-21）
  — 根拠が二次加工（パーサー推定、カバー率97.1%）で
  約290件が判定不能、代替なし、除外しなくても害がない
```

日付がないと、状況が変わっても永久に有効な不文律のようになってしまう。

## 5. 競合比較で機能のアイデア出し

Claude に競合サイトを分析させ、「何が負けているか」を聞く。ただし「負けている」= 実装すべきとは限らない。各項目について「深く検討して」を使い、本当に実装すべきかを検証する。

## 6. フィードバックは正本規約と hook に投資する（memory ではない）

Claude が同じミスを繰り返した時、memory (`~/.claude/` の memory 機能) に feedback として保存するのが反射的な対応だが、**しない**。このリポの `memory-guard.sh` hook が memory directory への feedback 系書き込みを実際に deny する。理由は precedent-as-training-data — memory に書かれた feedback は毎セッション load されて pattern-match を強化し、是正より反復の方向に働く。詳細な理論は [`convention-design-principles.md`](convention-design-principles.md) §8.3。

durable な修正先は**マシン・セッションを越えて残る場所**に置く:

- **一般化できるルールは [CONVENTIONS.md](../CONVENTIONS.md) または `conventions/*.md`** — git 同期、全 session で load、編集可能、CLAUDE.md から pointer で参照される。「常に X をする」「Y を絶対にしない」類の rule の正当な置き場。
- **catastrophic 級のリスク（データ破壊・secret leak・不可逆な外部通信）は hook** — PreToolUse `deny` / pre-commit ブロック / permission allowlist。§8.2 が介入強度のランキング、§8.4 が「どんな written rule より機械的強制の方が構造的に強い」理由を説明。
- **annoyance 級のミス（数文字の訂正で済むもの）はどこにも書かない** — in-session correction で受容して終わる（§9.1 triage）。ここで memory に手が伸びるのは、工学的判断ではなく不安応答であることが多い（§8.5）。

元の観察 — 修正ばかりだと Claude が過度に慎重になる — は依然有効。非自明だがうまく機能したパターンは「やるな」ルールと並べて同じ正本規約に書き添える。修正例と成功例のバランスは正本規約の中で取る — memory に置くと load-and-repeat ループが密度の高い側を増幅してしまう。

## 7. 正本を1つに決め、循環参照を潰す

情報の置き場所を1つだけ決め、他は参照にする。参照先はセクション名まで明記する:

```markdown
# 悪い例（循環参照）
CONVENTIONS.md: 「リポ一覧の正本は MEMORY.md」
MEMORY.md: 「リポ一覧は CONVENTIONS.md §1 が正本」

# 良い例（正本が1つ）
CONVENTIONS.md: 「リポ一覧の正本は MEMORY.md の『リポ一覧（正本）』セクション」
MEMORY.md → [実際のリポ一覧テーブルがここにある]
```

## 8. サブプロジェクトの CLAUDE.md チェーンに注意

Claude Code は作業ディレクトリから親方向に `CLAUDE.md` を全て auto-load する。`~/Claude/repo/sub/` で作業すると、`~/Claude/CLAUDE.md`・`~/Claude/repo/CLAUDE.md`・`~/Claude/repo/sub/CLAUDE.md` の 3 つが同時に載る。これは特に 200K コンテキストモデルで効いてくる — autocompact が 167K トークン付近で発火するため、チェーンが膨らむとセッション開始前に余裕を食い潰してしまう。

各階層を役割ごとに分離する:

- **トップレベル `~/Claude/CLAUDE.md`** — 身元・全体規約・リポ索引。
- **リポ `CLAUDE.md`** — リポの概要・起動方法・詳細への pointer。
- **サブプロジェクト `CLAUDE.md`** — コマンド・特有の注意・アーキ超要約（5〜8 項目 × 1 行 + `docs/architecture.md` への pointer）。80〜100 行目安。

重い narrative・パラメータ表・設計根拠は `docs/`（auto-load されない）に置いて pointer で参照する。原則と事例は [`convention-design-principles.md`](convention-design-principles.md) §10.10–10.11。
