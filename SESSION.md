# SESSION — claude-config

## 現在の状態
**完了**: 公開リポ leak 防止システム全 5 セッション実装完了 (2026-04-09〜10)。Tier A regex hook + pre-commit Tier B literal check + audit + marker 12 repo 展開 + setup.sh Step 8 追加 + 週次 scheduled-task 登録。

## 今セッションの変更（2026-04-09〜10）

### 公開リポ leak 防止 — 設計・実装・全 repo 展開

**契機**: LorentzArena (public) で組織環境を暗示する間接表現が 5 ファイル 16 行に累積していた (commit `ae25604` で修正済み)。Claude 側は catch できていなかった。

**設計**: `sensitive-repo-patterns.ja.md §3-3` 優先で構造制約 hook と情報配置分離の 2 本柱。5 セッションで段階実装。詳細は DESIGN.md §公開リポ leak 防止。

**成果物 (主要)**:
- `hooks/public-leak-guard.sh` — PreToolUse Tier A regex
- `scripts/public-precommit-runner.sh` — pre-commit Tier A + literal ephemeral
- `scripts/install-public-precommit.sh` — 冪等 stub installer
- `scripts/audit-public-repos.sh` — 定期 sweep
- `.claude/public-repo.marker` — 12 public repo に設置
- `setup.sh` Step 2 + Step 8 更新
- `odakin-prefs/sensitive-terms.txt` (gitignore + network-notes git-crypt symlink) + `work-network.md` placeholder 化
- `odakin-prefs/leak-incidents.md` + `next-steps.md`
- scheduled-task `public-repo-leak-audit-weekly` (毎週月曜 09:23)

**初回 audit 結果**: 12 repo scan、hit 10 sections (全て既存、受容判断済み)、missing markers 0。`leak-incidents.md` に初回 audit エントリ追記済み。

## 過去セッションの変更（2026-04-09 前半）

docs: add sensitive-repo-patterns (ja/en) — 機密情報を含むリポの設計パターン集を `docs/` に追加。conventions: Substack 取得と Gmail MCP read_email の大容量出力パターンを `conventions/substack.md` に記録。

## 過去セッションの完了事項 (詳細は git log + DESIGN.md)

- **2026-04-08**: git-state-nudge.sh に STALE_DIRT 検出追加 (porcelain-hash-age、5 シナリオ検証済)。arxiv-digest cron 根治 (b8f1539)。DESIGN.md に設計判断 90 行追記
- **2026-04-07 夜**: git-state-nudge.sh 拡張 (orphan-tree 検出、noise 削減、update notifier、private リポ名 sanitize)
- **2026-04-07 朝〜昼**: dropbox-refs convention 新規追加 + 3 ラウンド 4 軸チェック
- **2026-04-06**: ARCHITECTURE.md / RUNBOOK 位置づけ決着、CONVENTIONS §2 表の個人層移管、DESIGN/EXPLORING 分離
- **2026-04-03**: PATH 二層防御 (.zprofile + REQUIRED_PATHS snapshot patch)

## 残タスク

- [ ] **RUNBOOK 系ファイルの実例運用後再検討**: トリガーは「いずれかのリポで CLAUDE.md からランブックを切り出す具体的ニーズが出たとき」。詳細は DESIGN.md「RUNBOOK 系ファイル」セクション参照
- [ ] **規約 rollout 原則の一般化の再検討**: case 2 発生 (RUNBOOK 導入 or 他 content-reorganization 系 convention 追加) で一般原則 (principles §7 新設など) に昇格するか再判断。1 データポイントでの formalize は YAGNI で defer 中
- [ ] **principles.md 昇格候補 4 件の再判定**: 2026-04-08 の STALE_DIRT 関連作業で浮上した 4 原則 (Narrower-but-active、Generator owns commit、Event-driven vs time-driven safety net、Multi-commit workflow checkpoint) の再発時昇格。詳細と un-defer トリガーは `DESIGN.md` 末尾「検討事項: principles.md への昇格候補」参照。**最 strong** は Event-driven vs time-driven (既に対比表あり)、最新で 1 データポイントしかないが緊急性が高いのは Multi-commit workflow checkpoint (人間の指示無しで Claude 自身が横断 sweep を実行する習慣づくり)
