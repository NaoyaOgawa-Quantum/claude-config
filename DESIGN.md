# DESIGN — claude-config

設計判断とその理由を記録する。

---

## PATH 管理: 二層防御の設計

Claude Code の Bash ツールは起動時に生成したシェルスナップショットを source する。スナップショットの `export PATH=...` がセッション中の PATH を決定するため、ここで PATH が壊れると全コマンドに影響する。

### 根本原因と第1層（.zprofile 修正）

**判断:** `.zprofile` から `brew shellenv` を削除し、PATH 設定を `~/.zshenv` に一元化。

**Why:** macOS login shell は `.zshenv` → `/etc/zprofile` → `~/.zprofile` の順に実行する。Homebrew の推奨設定（`eval "$(brew shellenv)"`）を `.zshenv` と `.zprofile` の両方に書くと、`.zprofile` 内の `path_helper`（`PATH_HELPER_ROOT="/opt/homebrew"` 付き）が `/opt/homebrew/etc/paths`（brew の bin/sbin のみ）から PATH を再構築し、`.zshenv` の if-blocks で追加した TeX・Python 等を消す。

`/etc/zprofile` の **system** `path_helper` は `/etc/paths.d/TeX` 等を読むので、login shell でも TeX は通る。`.zprofile` で再度 brew 版を呼ぶ必要はない。

**trade-off:** `.zshenv` は全 shell type で実行されるため、non-interactive shell でも brew が PATH に入る。これは Claude Code にとっては望ましい。Terminal.app のログインシェルでも問題なし。

### 第2層（スナップショット自動パッチ）

**判断:** launchd WatchPaths を採用。PreToolUse フックは棄却。

| 方式 | Bash オーバーヘッド | 仕組み |
|---|---|---|
| PreToolUse フック | ~0.05秒/回 | 毎 Bash 呼び出しで zsh を起動しパッチ済みか確認 |
| **launchd WatchPaths** | **0秒** | スナップショット生成をディレクトリ監視で検知、自動パッチ |

**Why:** スナップショットはセッション開始時に1回だけ生成される。修正も1回でいい。毎回の Bash 呼び出しでチェックするのは設計として間違い。zsh 起動コスト（~0.03秒）はスクリプト内の最適化では消せない。

**setup.sh への組み込み:** Step 2b で launchd plist を自動インストール（macOS のみ）。冪等性あり — 既にロード済みならスキップ。

### パッチスクリプトの設計: REQUIRED_PATHS 方式

**判断:** 固定 FULL_PATH の全置換ではなく、REQUIRED_PATHS リストによる不足検出・追加方式を採用。

**Why:**
1. **旧方式の脆弱性:** `grep 'export PATH=/usr/bin'` でマッチして `sed` で全置換していたが、Claude Code v2.1.87 でスナップショットの PATH 形式が変わり（先頭が `/usr/bin` ではなくなった）、パッチが効かなくなった。
2. **FULL_PATH のメンテナンス忘れ:** FULL_PATH に TeX を書き忘れていて、パッチ自体が不完全な PATH を上書きしていた。
3. **REQUIRED_PATHS 方式の利点:** 各エントリの実在チェック付きで不足分だけ追加するため、Claude Code の形式変更に耐性がある。既存の正しいエントリを壊さない。

**メンテナンスルール:** 新しいツールをインストールして PATH に追加する場合、`fix-snapshot-path-patch.sh` の REQUIRED_PATHS 配列を更新すること。

---

## 危険コマンドのブロック: deny ルール vs PreToolUse フック

**判断:** settings.json の deny ルールのみ。フックは不要。

**Why:**
1. deny ルールはフックより先に評価される。deny で拒否されたコマンドはフックに到達しない
2. つまりフックは常に死んだコードになる
3. 0.015秒/回のオーバーヘッドに見合う価値がない

当初 dangerous-commands-guard.sh を「二重防御」として残したが、deny ルールが先に評価される以上、フックが発火する状況は存在しない。背景は conventions/shell-env.md に文書化済みなので、スクリプトとして残す理由もない。削除した。

**deny ルールのパターン選定:**
- `Bash(*tccutil*)` — 広いパターンだが、Bash で tccutil に言及する正当な用途は全て Grep/Read ツールで代替可能。実害ゼロで最大安全性。

---

## ARCHITECTURE.md: 必須化せず任意ファイルに留める

**判断:** §2 の必須ファイル（CLAUDE.md / SESSION.md / DESIGN.md / .gitignore）は変更しない。ARCHITECTURE.md は §2 の「任意ファイル」サブセクションに 5 行で位置づける（作る基準・作らない場合・前例リンク）。

**Why:** 2026-04-06 に全 30 リポの CLAUDE.md を行数・コードファイル数・見出しで実地レビューした結果:

1. **適用範囲が狭い:** ARCHITECTURE.md が筋良く効くのは ~3-4 リポのみ（LorentzArena / mhlw-ec-pharmacy-finder / arxiv-digest など複数レイヤを持つコードリポ）。残り 26-27 リポは LaTeX 論文・記事・データ運用・薄いスクリプト集で、構造説明が CLAUDE.md の表 1 つに収まる。必須化すると形だけのファイルが量産され、`docs/convention-design-principles.md` §3「過剰規約の害」と直接衝突する。
2. **CLAUDE.md 肥大化の救済策にならない:** 行数トップ群（300 行超 2 件、120-200 行 3 件）の見出しを精査すると、嵩を稼いでいるのは「動作プロトコル」「更新手順」「rotate チェックリスト」など**ランブック系**であって、構造説明ではない。ARCHITECTURE.md を切り出してもこれらは減らない。
3. **§2 役割定義との衝突:** CLAUDE.md の役割に「構造」が既に含まれている。ARCHITECTURE.md を必須化すると CLAUDE.md の役割定義を書き換える必要があり、既存 30 リポに波及する。
4. **実例不足:** 「ARCHITECTURE.md がなくて困った」事例は LorentzArena 1 件のみ。規約は実例から抽出するのが原則（`convention-design-principles.md` 冒頭）。1 サンプルでの規約化は早い。

**棄却した代替案:**
- *全リポ必須化:* 上記 1, 3 で却下
- *コードリポ限定で必須:* 「コードリポ」の判定基準（src/ の有無、ビルドコマンドの有無）が曖昧で揉める。CONVENTIONS の精神（機械的に適用できるルール）に合わない
- *§2 に何も書かず LorentzArena の個別最適に留める:* 同じ判断を別リポで再びするコストを避けるため、最低限の指針は明文化する

**作る基準の言語化:** 「コードリポで CLAUDE.md の構造説明が表 1 つに収まらず、ファイル名やクラス名から関係性が読み取れない場合」。否定形（作らない）も併記して、LaTeX/記事/データ運用リポで迷わないようにする。

---

## RUNBOOK 系ファイル: 規約化を待つ（実例先行）

**判断:** §2 に追加しない。`docs/runbook-*.md` 等の任意ファイル化も今は明文化しない。SESSION.md の残タスクとして「実例運用後に再検討」を残す。

**Why:** ARCHITECTURE.md の検討中に副産物として浮上した論点。CLAUDE.md 肥大化の真因がランブック系と判明したが、即規約化すべきではない:

1. **境界が曖昧:** データ運用リポの「一括更新手順」（150 行近いスクリプト群）、設定リポの secret rotate チェックリスト、multi-agent-shogun の Communication Protocol — これらは粒度・性質が大きく異なる。「ランブック」という単一概念で括れるか実例で確かめる必要がある。
2. **既に CLAUDE.md で動いている:** 上記はいずれも CLAUDE.md に書かれた状態で運用が回っている。困っているわけではない。先に規約を作ると「切り出すべきか否か」の再判断コストが発生する。
3. **ARCHITECTURE.md と同じ轍:** 1 サンプルでの規約化を避ける原則を、自分自身でもう一度踏んではいけない。実例 2-3 件で運用してから抽象化する。

**次の判断トリガー:** いずれかのリポで CLAUDE.md からランブックを切り出す具体的ニーズが出たとき（例: 一括更新手順が拡張されてさらに肥大化、または別端末からの実行で手順が壊れる事故）。そのとき DESIGN.md にこの欄を更新し、規約化判断を再開する。

---

## CONVENTIONS.md §2 記録判別表: user-specific instance を除去

**判断:** §2 の「記録先の判別」表から「特定ドメインの参照データを特定の private リポの管理ツールに送る」instance 行を削除。同等のルールは個人規約リポ (odakin-prefs) に専用ファイルとして移管した。

**Why:** 元の行は表の他の行 (普遍的な情報種別 → 記録先の対応) と性質が異なり、user-specific な instance を universal table に混入させていた。匿名化するだけでは構造的問題が残る:

1. **table の同質性が崩れる:** 他の 6 行はどれも universal な対応 (例: 「設計判断 → DESIGN.md」)。問題の行だけが特定のリポ・特定のスクリプトを名指ししており、claude-config を clone する他の利用者には無意味
2. **public リポに private リポ名が露出:** 名指しされていた管理リポは private。claude-config の安全規則 (CLAUDE.md) は非公開リポ名のコミットを禁じており、その例外リストにも該当しない
3. **一般化しても情報密度が失われる:** 「ドメイン固有の参照データは専用ツール参照」のような曖昧化では実用価値ゼロ

**移管先の選定:** 候補は (a) odakin-prefs/CLAUDE.md (private cross-machine 個人規約), (b) memory (~/.claude/...), (c) 該当 private リポの CLAUDE.md。

- (b) memory はルール定義の置き場ではない (`docs/convention-design-principles.md` §5)
- (c) 該当 private リポの CLAUDE.md に置くと、同ドメインの他リポで作業中にこの横断ルールが見えない (リポ単位のスコープでは届かない)
- (a) odakin-prefs は cross-machine な個人規約のために設計された場所であり、最も適合する

**odakin-prefs 側の構造:** odakin-prefs/CLAUDE.md は「1 ルール = 1 ファイル」「テーブルに載っているファイルだけが実効的」という原則を持つ。これに従い専用ファイルを新規作成し、CLAUDE.md のテーブルに追記した。

---

## ~/Claude/CLAUDE.md の symlink 化 (完了 2026-04-06)

**実行結果:** 戦略 **(b) 個別ファイル化 + symlink 置換** を採用して実行完了。`~/Claude/CLAUDE.md` は `odakin-prefs/CLAUDE.md` への symlink に置換済み。

**移管マッピング:**

| 旧 `~/Claude/CLAUDE.md` のセクション | 移管先 |
|---|---|
| 作業ディレクトリ宣言 | `odakin-prefs/project-structure.md` |
| プロジェクト構成ルール | `odakin-prefs/project-structure.md` |
| preview_start リンク出力ルール | `odakin-prefs/project-structure.md` (bundle) |
| ユーザー情報 (氏名・所属・メール) | `odakin-prefs/user-profile.md` |
| CONVENTIONS.md 参照リスト | `odakin-prefs/CLAUDE.md` 本体「規約参照」セクションに統合 |

**bundling 判断の根拠 (詳細は odakin-prefs DESIGN.md 該当セクション):** 「1 ルール = 1 ファイル」の厳格適用は 1 行ファイルを生む。pragmatic relaxation として「関連密接かつ合計 10 行未満」のルールは bundle 可とした。`project-structure.md` がこれに該当 (作業ディレクトリ + 配置 + preview)。

**setup.sh step 7 (CLAUDE.md user-facing 番号) への影響:** 既存設計のまま機能する。新規端末では `odakin-prefs` clone 後、setup.sh 内の Step 5a (`setup.sh` L460-481) が `~/Claude/CLAUDE.md` (target なし or regular file) を symlink に置換する。本セッションの symlink は手動 `rm + ln -s` で作成したため、setup.sh 自身の冪等性 (regular file 上書きパス) の実地検証は次回 setup.sh 実行時に行う (TODO)。

**今回の手動操作:** 旧 regular file は `~/Claude/CLAUDE.md.pre-symlink-backup` に退避後、symlink 経由読み込みを確認したうえで削除済み。

---

## claude-config git history scrubbing (確定: 見送り 2026-04-06)

**判断:** 見送り。HEAD クリーン化で実用的な対応は完了したと見なす。下記の trade-off 分析を踏まえてユーザーと再確認のうえ確定。

**経緯:** 2026-04-06 に CONVENTIONS.md §2 記録判別表から特定 private リポを名指しした行を削除した。HEAD は既にクリーンだが、過去の commit には削除前の状態が残っている (`git log -p CONVENTIONS.md` で特定可能)。

**手段の選択肢:**

- `git filter-repo --replace-text` (推奨。filter-branch より高速・安全)
- `git filter-branch --tree-filter` (古い方法、どこでも動く)
- BFG Repo-Cleaner (file 単位の置換に便利、文字列単位はやや弱い)

**リスクと制約:**

1. **force-push が必要**: 公開リポへの force-push は安全規則 §5.3 で原則禁止。`--force-with-lease` でも履歴書き換えには変わりない
2. **他端末 clone との不整合**: 他のマシン (別 PC) で同じリポを clone している場合、pull が失敗するか歴史が分岐する。再 clone が必要
3. **外部キャッシュは消えない**: GitHub 自身の cache, fork, web view, archive.org, Wayback Machine, GitHub Code Search index, 各種 mirror に既に取り込まれている場合は除去できない。force-push しても "完全削除" は達成不可能
4. **commit hash の変動**: 外部から該当 commit を参照しているリンク (PR コメント、blog post、issue 等) はリンク切れになる

**価値の評価:**

- HEAD は既にクリーンで、public リポを訪れる人は基本的に HEAD のみ閲覧する → 実用上の安全性は確保済み
- 「string が史的に存在した」という事実は変えられない → scrubbing しても完全な秘匿は不可能
- リスク (force-push, 他端末との不整合, 外部キャッシュ残留) が利得 (HEAD 以外の閲覧経路の遮断) を上回る

**実行を再検討するトリガー:**

- 文字列検索などで該当 private リポ名が外部から実際に発見・言及された
- "完全クリーン" に強い意向が新たに発生した
- 上記以外のタイミングでは検討しない (スコープ外)

---

## CONVENTIONS.md / conventions/ 内の自己言及的 odakin 記述 (確定: 現状維持 2026-04-06)

**判断:** 現状維持。意図的設計として残す。下記の trade-off 分析を踏まえてユーザーと再確認のうえ確定。

**該当箇所** (2026-04-06 grep 結果):

| 場所 | 内容 | 意図 |
|---|---|---|
| `CONVENTIONS.md` L10 | `/Users/odakin/` をパス例として明示 | パス記述ルールの**反例**として使用。「ユーザー固有絶対パスを書かない」原則を可視化 |
| `conventions/latex.md` L16-18 | JHEP.bst「個人的好み」、setup.sh の odakin-only 自動インストール | .bst 自体が public リポ内に置かれており、由来 (個人趣味) を honest に文書化 |
| `conventions/research-email.md` L41 | `assignee: odakin | collaborator_id` 例示 | スキーマ説明の例示。匿名化すると意味が伝わらない |
| `conventions/scheduled-tasks.md` L58 | 「現運用者(odakin)の全マシン」 | パス hardcode を選んだ理由として、現運用者が 1 人であることを正直に文書化 |

**性質:** これらは「private 情報の leak」ではなく「設計選択」。claude-config は odakin の流儀を public に展示するリポであり、運用者として odakin を例示することは設計目的と整合する。

**削除を検討すべきトリガー:**

- odakin 以外の co-maintainer が増えた
- claude-config を template として使う他ユーザーが現れた (流儀の押し付けを避けたい)
- 上記以外のタイミングでは現状維持

**棄却した代替案:**

- *全てを完全匿名化:* 設計判断の why が伝わらず、文書としての価値が下がる
- *private 化:* claude-config を public にしている目的 (公開展示 + 他ユーザーへの参考) と矛盾

---

## DESIGN.md と EXPLORING.md の分離（2026-04-06）

### What

- `CONVENTIONS.md §2` の DESIGN.md 定義を「**決定した**設計判断（defer 含む）」に絞る
- 任意ファイル `EXPLORING.md` を新設（ARCHITECTURE.md と同じ「任意ファイル」扱い）。未決定の思考・代替案・option space の棚卸し用
- 境界判別・lifecycle・3 カテゴリ分析・棄却した代替案の詳細は `docs/convention-design-principles.md §6` を正本とする（重複を避けるためここでは書かない）

### Why（ここに書く最小限）

原則・3 カテゴリ分析の全文は `docs/convention-design-principles.md §6` 参照。**このファイルには決定固有の context だけを残す**:

- **トリガー**: LorentzArena 2+1/DESIGN.md が 500+ 行に肥大化し、「残存する設計臭 defer」（決定記録）とスマホ UI 思考メモ（未決定）を同時に書く必要が生じた場面
- **気づき**: DESIGN.md が既に「決定記録 / 未決定探索 / メタ決定（defer）」の 3 カテゴリ dumping ground になっていた（2+1 の用語再考セクションが前例として既に存在）
- **選択**: 2 ファイル分割（決定 vs 探索）。3 ファイル分割やタグ付けは却下した（詳細は principles §6）

### 初回適用

- **2026-04-06**: `LorentzArena/2+1/EXPLORING.md` 新規作成。スマホ UI の設計思考を収容
- **2026-04-07** (4 軸レビュー追加修正): 初回適用リポ内で用語再考セクションが DESIGN.md に orphan bullets として残っていた問題を検出し、同日 `2+1/EXPLORING.md` に migrate した
  - 経緯: `88ed267` (2026-04-06) で残存する設計臭セクション追加時に `### 用語の再考` ヘッダーが誤って置換され、bullets が orphan 化していた。cadf135 の defer 拡張でさらに文脈から離れた
  - 判断: 「retroactive migration はしない」の対象は **他リポ**。初回適用リポ内の既存 (b) コンテンツは EXPLORING.md 新設タイミングで同時 migrate するのが自然（1 件だけ例外にすると規約 purity を自ら毀損）

### 適用方針（簡潔版）

詳細は `docs/convention-design-principles.md §6` 参照。要点:

- **他リポへの retroactive migration はしない**: 既存の既存 DESIGN.md は触らない
- **新規探索が発生したリポから順に導入**: 上記 LorentzArena 2+1 が初回
- **小リポ・決定しか書かないリポでは不要**: EXPLORING.md は任意ファイル

---

## hooks/ の役割分担

| ファイル | 呼び出し元 | 役割 |
|---|---|---|
| memory-guard.sh | PreToolUse (Edit/Write) | メモリディレクトリへの書き込み前に §2 判別を強制 |
| memory-guard-bash.sh | PreToolUse (Bash) | Bash 経由のメモリ書き込みを警告（0.005秒/回） |
| fix-snapshot-path-patch.sh | launchd WatchPaths | スナップショット PATH を REQUIRED_PATHS 方式で自動補完（Bash に介入しない） |

Bash の PreToolUse フックは memory-guard-bash.sh のみ（0.005秒/回）。

---

## dropbox-refs convention: per-repo symlink + personal-layer registry (2026-04-07)

### What

複数の git リポから「Dropbox の特定フォルダにある共同 PDF」を、リポ内の安定した相対 path (`./dropbox-refs/`) で参照する規約。詳細は `conventions/dropbox-refs.md`。

### Why (ここに書く最小限)

- Dropbox の install 場所が OS / Dropbox バージョン / multi-account 構成で違う
- subpath は user 固有 (collaborator ごとに Dropbox 内の階層が違う可能性)
- 共有リポに絶対パスや user 固有 subpath を書くと共同編集者の環境で壊れる
- 同パターンを複数の共同研究で再利用したい

### 検討した代替案と却下理由

| 案 | 内容 | 却下理由 |
|---|---|---|
| (A) 各リポに setup.sh を持たせて `~/Dropbox` 固定で symlink | 実装最小 | `~/Dropbox` 固定が壊れるユーザー環境 (macOS Sonoma+ CloudStorage、business アカウント、Linux) でフェイル |
| (B) global mount: `~/Claude/.dropbox -> $DBROOT` を 1 本作る | symlink 1 本で済み、registry 不要 | サブフォルダ rename 時に各リポの参照を grep 修正する必要、ASCII clean な canonical 名を経由できない |
| (C) env var `$DROPBOX` をシェルで定義してドキュメントに書く | OS-agnostic | TeX や file manager は env var を展開しない、tilde-expansion のほうが互換性高い |
| (D) Git LFS で PDF をリポに入れる | クローンするだけで PDF 入手 | LFS quota、PDF が repo 履歴に固定、共同編集者の LFS install 必須 |
| **(E, 採用) per-repo symlink + personal-layer registry** | リポ root に gitignored `dropbox-refs/` symlink、registry は personal layer に YAML で持つ | 各案の欠点を回避、TeX や relative path も動く、whole-repo Dropbox パターンと自然に共存 |

### 設計判断の小項目

- **registry format: YAML**（vs TSV）: 当初 TSV を提案したが、ユーザー要望で YAML に変更。理由は (1) 拡張性（将来 description / provider / tags 等を追加可能）、(2) 構造化が自然、(3) PyYAML が macOS / Linux で簡単に手に入る。代償は PyYAML 依存だが convention doc §3.2 で明記
- **registry の置き場: personal layer**（vs 各リポ / claude-config）: subpath は user 固有なので shared/public に置けない。personal layer は per-user / cross-machine な Dropbox layout を表現できる唯一の層
- **mount point name: visible `dropbox-refs/`**（vs hidden `.refs/`、global `~/Claude/.dropbox`）: ユーザー要望で visible。リポ内に置くことで ASCII 名 + `~` 展開不要 + relative path で参照できる
- **trigger: claude-config setup.sh + personal-layer post-merge hook**（vs SessionStart hook、手動）: SessionStart hook は claude-config DESIGN.md の既存判断 (UI notification ノイズで削除済み) と矛盾するので避けた。手動だと忘れる。setup.sh + post-merge は idempotent + git pull の自然な拡張
- **post-merge hook: tagged で常に refresh**（vs 一度 install したら触らない）: layer 移動や script 場所変更で hook 内の絶対 path が古くなる問題を防ぐため。tagged ("managed-by:" マーカー) hook は claude-config が所有しているので再書き込みは安全。tag が無い hook はユーザー手書きとして保護
- **dropbox-root.sh の resolution chain**: `$DROPBOX_ROOT` → `~/.dropbox/info.json` (`personal` → `business`) → `~/Dropbox` → `~/Library/CloudStorage/Dropbox` → `~/Library/CloudStorage/Dropbox-Personal`。最初は環境変数 override を許し、次に Dropbox 公式の info.json (最も authoritative)、最後に既知の install 場所。非 Dropbox cloud に移行する場合はこの resolver を別のものに差し替える

### 副次的な migration: 既存 whole-repo Dropbox リポの脱 Dropbox-symlink (同日、途中で revert)

新 dropbox-refs 規約の導入と同時に、ある既存リポを whole-repo Dropbox パターン (`~/Claude/<repo>` が Dropbox folder への symlink、以下 **Pattern A**) から独立 git clone + `dropbox-refs/` 参照型 (**Pattern B**) に移行する作業も実施した。旧 Dropbox 側の `.git/` は削除して asset folder 化、新 clone から `./dropbox-refs/` 経由で sibling フォルダ群 (参照 PDF・notebook 等) を参照する形に統一。

**同日夕に Pattern A へ revert**。理由:

- 移行後に作業ツリー (`~/Claude/<repo>/`) と asset folder (旧 Dropbox working tree) に、7 つの source ファイル (本文 tex、bib、bst、build output pdf、図、検証 script、メモ) が丸ごと duplicate する状態が発生した。`cp -r` 相当で作業ツリーを seed したときに asset folder 側の source を消さなかったため
- duplicate 自体は一方を消せば解消するが、**リポ固有の事情: 共同編集者とは git push/pull 経由のみ** (Dropbox folder は共有していない)。この場合 Dropbox 内の `.git/` を multi-machine が同時に触る可能性が無く、Pattern A 採用上の主要リスク (Dropbox 同期が `.git/` を破壊する事故) が発生しない
- Pattern A のほうが source と asset が同じディレクトリに同居でき、`./foo.pdf` や `../sibling/` の素朴な相対 path で全部触れる。`dropbox-refs/` symlink の layer が消えるぶん mental model が簡単

この経験から、dropbox-refs convention は **「どちらを選ぶか」の決定基準を明示**する必要があると判明。`conventions/dropbox-refs.md` の冒頭に Pattern A vs B の選択ガイドを追加した。

### Pattern A vs B の決定基準 (2026-04-07 夕 追加)

| 条件 | 推奨 | 根拠 |
|---|---|---|
| 共同編集者と Dropbox folder を共有し、複数 machine で同時に `.git/` を触る可能性あり | **B** | Dropbox 同期 race が `.git/` object store を壊すリスクが実在 |
| リポが multi-machine で同時編集される (solo でもラップトップ + デスクトップ併用等) | **B** | 同上 |
| 共同編集者はいるが git push/pull 経由のみ (Dropbox folder は share しない)、かつ同時編集マシンは実質 1 台 | **A** | Dropbox 同期 race が発生しえないので A のほうが単純 |
| solo 運用、Dropbox は単に自分の素材置き場 | **A** | 同上 |
| リポが arXiv cite だけで完結 (Dropbox の参照 PDF を触らない) | **どちらでもない** | 普通に `<base>/<repo>` に clone すれば十分 |

**Trade-off の本質**: Pattern B は `.git/` を Dropbox の外に出すことで同期 race を根本的に排除する代わりに、source と asset の場所が分離して dropbox-refs symlink という layer が増える。Pattern A は layer が少ないが Dropbox 同期が `.git/` を触る前提になる — 複数 machine が同じ `.git/` を同時に書くと壊れるので、同時編集の有無が分水嶺。

**migration の落とし穴**: B → A に revert する際は、(i) `.git/` を Dropbox tree にコピーしたあと `git checkout -- .gitignore .gitattributes ...` で deleted tracked files を復元する、(ii) `dropbox-refs/` symlink と `.gitignore` の `/dropbox-refs` 行を削除する、(iii) `personal-layer/dropbox-collabs.yaml` から対応 entry を削除する、の 3 点をまとめて実行する。A → B の手順は dropbox-refs.md §3.4 参照。

## git-state-nudge.sh: cross-session WIP leakage の検出 — STALE_DIRT (2026-04-08)

### What

`hooks/git-state-nudge.sh` の case (3) (first-sighting) に **STALE_DIRT** という新しい dirty signal を追加した。発火条件は「`git status --porcelain` の出力 (= 「dirty file の集合」を表す文字列) を sha1 化したものが、前回観測時から **24 時間以上不変**」。発火すると次の 1 行が emit される:

```
- N dirty file(s), unchanged set for ~Mh — possibly abandoned WIP from an earlier session
```

per-hash NUDGED guard (`$STATE_DIR/$REPO_HASH.stale-nudged`) で、同一 dirty set への repeat 警告は抑制される。working tree が clean になれば両 state file を破棄して各 dirty episode を independent に扱う。

### Why

2026-04-07 夜の noise 削減で case (3) から `DIRTY_COUNT > 0` 句を **完全削除**したため、AHEAD/BEHIND の無い純粋な dirty 状態は素通りする hole が生じていた。2026-04-08 朝の手動 sweep で、この hole から 2 件の cross-session WIP leakage が漏れていたことが発覚:

- **arxiv-digest**: 2026-04-02 〜 04-08 の 6 日分の cron 自動生成 archive json が uncommitted のまま蓄積 (15 ファイル)
- **ejp-revision**: 2026-04-07 の編集 (`combination_again.tex`/`.pdf`、`tasks.yaml`) が約 24h uncommitted

これらは「divergence」でも「直近 commit の未 push」でもなく、**前 session が dirty 状態を残したまま終了し、次 session でも誰も気付かない**という独立した failure mode。push-workflow.md の「セッション冒頭の sync 確認」「作業単位ごとの commit+push」は人間規律レベルの対策で、cron 由来の蓄積や Claude の取りこぼしには弱い。自動検知の safety net が必要。

### 検討した代替案と却下理由

| 案 | 内容 | 却下理由 |
|---|---|---|
| (A) 04-07 削除前の DIRTY_COUNT > 0 をそのまま復活 | 1 行修正 | 04-07 に「ノイズが多すぎる」として削除されたばかり。active WIP のたびに鳴る問題が再発する |
| (B) 「最新 mtime > Nh」(newest mtime semantic) | dirty file 中で最も新しい mtime が古ければ stale | **build artifact rebuild に騙される**。古い `.tex` を pdflatex で rebuild すると `.pdf` の mtime が "fresh" になり、本当に stale な `.tex` が見えなくなる (今回 ejp-revision の `.tex` + `.pdf` ペアがこの形) |
| (C) 「最古 mtime > Nh」(oldest mtime semantic) | dirty file 中で最も古い mtime が閾値超えなら stale | active な multi-day refactor (古い + 新しい dirt が混在) と「古い編集 + 新しい build artifact」(これは warn したい) を区別できない。両方とも「最古 mtime が古い」になる |
| (D) 朝の health check scheduled task | cron で全 repo を `git status` 走査して報告 | 04-07 夜の twcu-seminar postmortem で **既に却下済み** (時間ベース、重い、既存 hook の first-sighting fetch と重複)。今回もこの理由は変わらない |
| (E) PostToolUse matcher を Read/Edit/Write にも拡張 | hook 発火頻度を上げる | 04-07 夜に既に却下 (typical workflow が Bash 主体、marginal value 小、overhead 累積) |
| (F) per-repo opt-out marker (`.no-stale-warn`) | scratch repo を除外 | 現状そんな repo が無く、YAGNI。per-hash NUDGED guard で実用上は十分静か |
| (G) hook 内で自動 commit してしまう | 検知だけでなく自動修復 | 自動 commit は意図のわからない変更を git history に流し込む。生成主体側で commit するべき (cf. 「Generator owns commit」原則、下記) |
| **(H, 採用) 「porcelain hash の age > 24h」** | dirty set そのものが string レベルで何時間不変かを測る | mtime 系の失敗 mode を全て回避。active 編集は dirty set を mutate するので hash が変わり age がリセット (= 元の noise 抑制が保たれる)、abandoned WIP は hash 不変 → age 蓄積 → 警告 |

### 設計判断の小項目

- **シグナルが mtime ではなく porcelain hash の age**: file 内容の rewrite に強い。本質的には「dirty 状態が文字列レベルで何時間 invariant か」を測っている。文字列の不変性は file content の不変性と独立しており、build artifact rebuild (内容 rewrite だが porcelain 行は同じ) も backup tool の touch も hash には影響しない
- **age の累積方法: state file の mtime を使う**: PORCELAIN_FILE は hash が変わったときだけ書き直す (mtime 更新)。同じ hash を観測したときは file を touch しない → mtime が「初回観測時刻」のままに保たれる → `NOW - mtime` が age になる。time stamp を file の中に書く方式 (cross-platform `touch -d` の可搬性問題を避けるため) と同等の semantic だがより簡素
- **threshold: 24h**: 同一日内のセッション中断 (lunch/打合せ) を false positive にせず、「翌日まで持ち越した」を catch する自然な区切り。6h や 12h は long workday で false positive が増える、72h は abandonment を catch するのが遅すぎる
- **per-hash NUDGED guard**: HEAD-sha NUDGED guard (case 1, 2 用) と同じ思想を porcelain hash に適用。一度警告を出した dirty set には repeat しない。意図的に長期 dirty を残す scratch 運用 (今は無いが将来発生したとき) に対する低コストの noise 抑制
- **clean になったら state を破棄**: PORCELAIN_FILE と STALE_NUDGED_FILE 両方を `rm -f`。各 dirty episode を independent に扱うことで、(i) 過去に warn した hash が偶然再発生したときに沈黙させない、(ii) state file の累積を防ぐ
- **`shasum` / `sha1sum` fallback**: 既存 REPO_HASH 計算 (line 102-108) と同じ pattern。macOS は shasum、Linux は sha1sum、Windows Git Bash は両方。両方無いと PORCELAIN_HASH が空になり STALE_DIRT 検出は静かに無効化される (壊れず劣化)
- **case (1) ORPHAN_TREE / case (2) RECENT_COMMIT との priority**: STALE_DIRT は case (3) 内なので case (1)(2) より低 priority。orphan-tree や直近 commit が未 push な repo はそちらが先に発火する。case (1)(2) は return 0 で抜けるので、その session では STALE_DIRT は出ない (次回 first-sighting で出るチャンスを得る)。意味的には正しい priority (重大度: orphan > 直近未 push > 古い WIP)

### Bootstrap caveat (deliberate trade-off)

porcelain hash の age は **「初回観測時刻」を起点に始まる**。デプロイ時点で既に存在する dirty 状態は、この feature が初めて観測した瞬間に age 0 から始まるので、本当は 1 週間放置されてた dirt でも 24h 経過しないと警告されない。

mtime fallback で「初回観測時の oldest dirty mtime を bootstrap timestamp にする」という補正案も検討したが、

- mtime 系のシグナルを部分的にでも使うと案 (B)(C) の失敗 mode が部分的に再現する
- そもそも今回の sweep で全 repo を clean にしたので bootstrap 時に warn すべき dirt は存在しない
- 将来同様の事故が起きても 24h で catch されるので影響は限定的

として bootstrap 補正は **入れない** ことにした。code header と push-workflow.md に caveat を明記。

### 副次的な「Narrower-but-active > absent」原則

04-07 夜の DIRTY_COUNT > 0 削除は「シグナルがノイズすぎる」が理由だったが、04-08 で明らかになったのは **「ノイズなシグナルを削除すると、本来 catch したかった signal も一緒に失われる」** という当然の事実。

正しい対処は「削除」ではなく「**criterion を狭める**」: ノイズ要因を分析して、それを排除する narrower な criterion を見つける。今回は:

- 元のシグナル: `DIRTY_COUNT > 0`
- ノイズ要因: 「今書いてる active WIP が毎回鳴る」
- 区別したかった signal: 「abandoned, cross-session WIP」
- narrower criterion: 「dirty set が time-window 不変 (= 誰も触っていない) AND time-window > 1 日」

これは hook design 全般に適用できる原則として記録しておく価値がある。signal を消す前に「ノイズと本当に取りたい signal を区別する narrower criterion はないか」を必ず検討する。1 データポイントなのでまだ generalization としては弱いが、もう 1 件似たケースが出たら convention-design-principles.md に格上げを検討。

### Event-driven vs time-driven safety net

04-07 で却下した「朝の health check scheduled task」と STALE_DIRT は **似て非なるもの**:

| 軸 | 朝の health check | STALE_DIRT |
|---|---|---|
| 起動 | cron (時間ベース、ユーザー不在時も走る) | PostToolUse hook (Claude が Bash 叩いた瞬間) |
| 走査範囲 | 全 repo 一括 | cwd repo (+ literal `git -C <path>`) のみ |
| 副作用 | 報告生成 / SESSION.md 更新 / Claude 起動 | stdout 1 行を Claude session に inject |
| 重さ | 重い (全 repo `git status`) | 軽い (1-2 repo) |
| 精度 | high recall (全部見る) | event 駆動なので「触った repo だけ」に絞られる (low overhead) |
| 棄却理由 | 時間ベース、重い、既存 first-sighting fetch と重複 | 該当しない (event 駆動、軽い、first-sighting と協調) |

cron 系の安全網が却下されたからといって、event-driven な検出も自動的に却下されるわけではない。今後似た議論が出たときは「時間 vs event」の軸を最初に切り分けること。

### 関連 fix と responsibility split

STALE_DIRT は **汎用 safety net**。各 repo の root cause level の対処は別途必要:

- **arxiv-digest**: cron 自動生成の蓄積は STALE_DIRT で catch されるが、それは「警告」止まり。ファイルは依然 dirty。根治は arxiv-digest 側の `commit_archives_to_git()` (`src/archive.py`、commit b8f1539) で「生成主体が commit 主体」原則を実装した。STALE_DIRT は cron 系の generator にバグが残ったときの fail-safe として機能する
- **ejp-revision**: 人為編集の取りこぼしは generator がいないので STALE_DIRT が一義的な safety net。push-workflow.md の「TodoWrite で commit ステップを明示」も補完する人間規律レイヤー

責任分担の原則: **「自動で生成されるもの」は生成主体が commit 責任を持つ。「人間が編集するもの」は人間規律 + STALE_DIRT で catch する**。前者を後者に押し込むと永遠に dirty が累積する (今回の arxiv-digest が exactly そのパターンだった)。

関連 commit:
- `5ddd43f` (claude-config): STALE_DIRT 実装本体
- `b8f1539` (arxiv-digest): generator 側の root cause 対処
- `4257d0f` (odakin-prefs): push-workflow.md の `[git-nudge]` 警告 interpretation guide
