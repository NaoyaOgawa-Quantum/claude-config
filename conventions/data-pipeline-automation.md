# データ pipeline と半自動化の設計規律

下流自動化 (= build script / mirror script / template render) を伴うデータ管理で適用。 CLAUDE.md から参照: `~/Claude/claude-config/conventions/data-pipeline-automation.md`

ポスター・告知メール・web ミラー等を 1 source から自動生成する pipeline を構築するとき、 schema 不在期や judgment-required content の取り扱いで体系的な失敗が発生する。 本 convention はその回避規律を集約する。

---

## 1. データの単一ソース化 (= soft duplication 回避)

### 規律

**同じ事実を複数の file に書かない。 1 つの正本 (source of truth) を決め、 他は正本から render / transfer で生成する。**

例: ポスターの題名・概要・写真は **`<DB>.yaml` の field を正本**にし、 ポスター固有 yaml には title / abstract / photo を書かない (= 二重管理になり、 片方更新時に drift)。

### Why

- 同じ情報が 2 箇所に書かれると、 片方を update し忘れて drift する (= 体系的バグ源)
- 修正対象が増えると review コストが上がる
- 「どちらが正しい?」 の判断責務が user/Claude に転嫁される

### How to apply

- pipeline 設計時、 「この情報の単一正本はどこか?」 を最初に決定 (= schema 化)
- 下流の render / transfer は正本から **読むだけ** (write back しない)
- field の欠落が発覚したら正本に追加、 下流の重複は削除

### Pattern: schema 不在は下流自動化開始時に発覚する

schema 不在は **正本としての必要性が発覚する瞬間** = 下流自動化を始めた時に最も顕在化する。 例: ポスター生成 script を書こうとして始めて「abstract の正本がない」 と気付く。 これは正常な発見プロセス。 自動化を後回しにすると schema 不在も先送りになる (= log のような自由テキストに埋もれて構造化されない)。

「自動化要件は schema を厳密化する圧力」 として歓迎すべきで、 既存 free-text 運用を維持して「自動化は手間だから後で」 と先送りすると、 結果的に整合性管理コストが累積する。

---

## 2. forward-only schema migration

### 規律

**既存データを backfill しない、 次に touch する機会に新 schema へ refactor する。**

schema を拡張する時 (= 例: 候補 DB の新規 field 追加)、 既存全エントリを一気に backfill すると:

- 古い情報が不完全に転記される (= 内容欠落・判定ミス)
- 巨大な diff になり review 不能
- backfill 中の判断ミスは静かに drift する

代わりに **forward-only**: 既存 entry は触らず、 次に該当 entry を edit する機会 (= status 遷移、 update、 重要 event) で新 schema に refactor。

### How to apply

- 新 schema を確立 + 1 件 (= 当面必要な entry) のみに適用
- CLAUDE.md / DESIGN.md に「forward-only migration」 と明記 (= 将来の touch 時規律)
- 旧 schema と新 schema が **混在期** であることを許容 (= yaml で人間/Claude 両方読める = clean migration よりも safe)
- 一括 backfill task は「将来 TODO」 として明示記録、 ただし優先度低 (= forward-only で漸進的に解消される)

---

## 3. judgment-required content の placeholder pattern

### 規律

**AI が generate できない content (= judgment、 trust、 文体判断) は script 出力に placeholder marker を残し、 user が手で埋める。 完全自動化を無理に追求しない。**

例: 告知メールの「学生向け平易紹介」 段落は AI 初稿可能だが judgment required (= 文体 + 内容 reformulation + 親しみ度合い)。 script は `{{intro_paragraph}}` placeholder を残して draft 出力 → user が edit → 完成版を yaml field に保存 (= 次回 reproduce 可能)。

### How to apply

- script 出力に **placeholder marker** を残す (= 「`{{var: 説明}}` をここに」 形式で user に hint)
- placeholder が残っていれば script は **stderr で警告** (= 「<field> 未指定 → placeholder のまま出力」)
- 完成版を yaml field に保存 (= 次回再生成時に reproduce)

### Pattern: AI 初稿 → user edit → save back to source

完全手書き > 半自動 (= AI 初稿 + user edit) > 完全自動。 judgment required は半自動止まりで OK、 むしろ judgment を user に残す方が drift 防止に効く。

完成版を yaml field に **save back** すると、 次回類似 case で参照可能 + script で reproduce 検証可能 (下記 §5)。

---

## 4. script 入力の検証 (= input validation)

### 規律

**user input (= argparse 引数、 環境変数、 file path) は format を regex で validate、 不正値は explicit error で止める。 silent fallback しない。**

特に **filesystem path を構築する input** は path traversal を防ぐため strict validate。

```python
if not re.match(r"^\d{4}-\d{2}-\d{2}-[a-z][a-z-]*$", args.seminar_id):
    sys.exit(f"❌ seminar_id 不正: {args.seminar_id!r}")
```

### How to apply

- input 形式が固定 ID 系なら regex で validate
- pattern mismatch は `sys.exit` で early stop (= silent fallback で repo 外書き出しを防ぐ)
- error message に **期待 format と実際の値** を含める (= user が修正 hint を得る)

### Pattern: 必須 field 欠落も同様

データ正本に必須 field が欠落しているなら同じく explicit error:

```python
if not (candidate.get("title") or {}).get("ja"):
    sys.exit(f"❌ title.ja 不足、 candidates.yaml に転記が必要")
```

silent fallback (= `TBA` で render) は drift を隠す。 「データが揃ってないなら script は止まる」 が筋。

### Pattern: build → publish の責務分離

local build (= PDF/.tex 生成) と external publish (= 別リポへ mirror、 PDF copy) は別 script に分ける。 publish script は build 済 artifact の存在を前提に動き、 不在なら explicit error。 1 script に統合すると失敗時の責務切り分けが難しくなる。

---

## 5. 自動化機構の validity 検証

### 規律

**自動化 script を作ったら、 過去の手書き出力 (= user 承認済) を script で reproduce して完全一致を確認する。 mismatch があれば script の bug or 手書き drift。**

### How to apply

- 過去 user 承認済の出力 (= 送信済メール / 過去ポスター 等) を 1 件選ぶ
- その出力の input 条件 (= yaml field、 投稿日 等) を script の input に与える
- 出力を diff、 0 件なら validity 確認 ✓
- 差分があれば:
  - script の output format / template の bug を修正
  - or 過去手書きが流儀から drift していた (= 流儀を明文化する契機)

### Why

自動化機構を作っただけでは「動く」 が「正しい」 とは限らない。 過去手書き出力との完全一致は最も強い validity 証明 (= 「人間の OK judgement を script が再現できる」 = trust の根拠)。

### Pattern: judgment-required content の save back と validity 検証は相補

§3 の「完成版を yaml field に save back」 と §5 の「過去手書き出力を script で reproduce」 は同じ運用の表裏。 完成 content を yaml に保存 → script で再生成 → 完全一致確認 → 「次回類似 case で script を信頼して使える」 と確証。

---

## 6. 副作用つき自動 edit よりも reminder 出力

### 規律

**script が複数 file を update する責務を持つとき、 yaml への自動 edit (= round-trip 問題で comment / 整形が壊れる) よりも、 標準出力に reminder を print して手動更新を user に任せる方が clean。**

例: ミラー script が下流リポに file を生成・copy するのは OK、 上流 yaml への「mirrored_to」 field の自動追加は yaml round-trip で壊れる → 「下記 block を yaml に追記してください」 と stdout に print。

### Why

- yaml の round-trip は library 依存 (= ruamel.yaml 等)、 PyYAML だけだと comment が消える
- idempotency 維持が複雑化 (= 既存 field との merge、 ordering)
- user が確認できる surface に出す方が trust できる

### How to apply

- 副作用は「生成 / copy / delete」 等の coarse-grained action に限定
- fine-grained yaml field 編集は print reminder で user に任せる
- script 終了前に「変更されてない方の file」 と「user が手で update する内容」 を明示

---

## 7. 無人実行 (autonomous / scheduled) の gate

### 規律

**pipeline を cron/launchd 等で無人実行し、 結果を不可逆/外部な行き先 (= 共有・公開 repo への commit+push、 送信、 publish) に自動反映するなら、 §3 の「user が手で埋める / review する」 という run-time の人間 in-loop が無い。 そこで自動反映してよいのは「出力が入力の純粋な関数 = 推測ゼロ」 の変換だけ。 導出不能な field は (a) 人間が SoT に事前入力する (= その入力が「その item を publish してよい」 という per-item 認可になる) か、 (b) surface して人手に委ねる。 placeholder や推測を外部/公開 state に push しない。**

run-time に人間が居る半自動 (§3) では placeholder を出力に残して後で埋めればよい。 無人実行ではその猶予が無く、 placeholder/推測がそのまま公開面に焼き付く。 だから「武装 (armed)」 ゲートを設ける: **導出不能 field が SoT に揃った item だけ自動 publish、 揃わない item は surface のみ。**

### Why

- 無人実行 = 出力を誰も run-time に見ない → 誤りが公開面に直行する
- 「推測で埋める」 は不確実性を隠す assertion (= 出力が「確定情報」 に見えてしまう)。 機械翻訳した固有名詞 (例: 所属の英語表記) は典型的に誤る (= 公式名 vs 直訳)
- 人間が「導出不能な 1 field」 を埋める行為を per-item authorization に転用すると、 judgment は人間に残しつつ機械的組立ては自動化できる (= §3 の半自動を無人文脈に持ち込む橋)

### How to apply

- field を「導出可能 (= SoT の純関数)」 と「導出不能 (= 判断/翻訳/外部知識が要る)」 に分類
- 導出可能 field だけで full に組み立てられ、 かつ導出不能 field が SoT に**明示済**の item を「armed」 と判定 → 自動 publish
- armed でない item は surface (= 「この 1 field を埋めれば次回自動 publish」 と hint)、 **絶対に推測で埋めない**
- 「全 item を強制 armed 化する kill switch を false に」 等の全面手動 fallback も用意 (= 異常時の退避)
- 自動 publish した内容は事後に必ず通知 / log / git log で可視化 (= 無人でも誤 publish に早く気付ける)

### Pattern: 無人 commit も対話 session と同じ git 同期規律を mechanize する

無人 commit は「作業前に pull、 障害なら止める」 (= shared-repo / push-workflow の規律) を reflex でなく code で強制する。 公開 repo への非 fast-forward push / conflict / 壊れた build の流出を構造的に防ぐ:

1. `git fetch` → working tree が **clean ∧ fast-forward 可能**でなければ apply 中止 (= dirty/diverge は人手に surface、 無人で merge しない)
2. mutate (= 生成 / copy)
3. **build / validate** (= 生成物が壊れていないか。 失敗なら `git checkout` + `git clean` で全 revert + push 中止 → 壊れた state を push しない)
4. commit (= 識別 prefix 付き、 例 `[<job>]`、 後で git log で grep 可能に)
5. push → race で reject されたら fetch + ff-pull + retry 1 回、 それでも駄目なら local commit を残して surface

clean 前提を preflight で保証してから `git clean -fd <dirs>` する設計なら、 clean は「自分が今作った untracked だけ」 を消す (= 既存 untracked を巻き込まない) ことが保証される。

### 関連

- §3 (judgment-required placeholder) = run-time 人間あり版、 本 §7 = 無人版。 同じ「機械は推測しない」 思想の対話/無人の両極
- §5 (過去手書き出力を script で reproduce) は無人 publish 前の validity 確認に必須 (= 生成物が手書き正本と同形式かを事前検証してから arm)
- 実行 locus の選択 (= そもそも無人 job を launchd / cron / scheduled task / GitHub Actions のどれで回すか) は [scheduled-tasks.md](scheduled-tasks.md) §「実行 locus で機構を選ぶ」
- 無人 job を「どのマシンで」 走らせるかの判定 + install 未済の surface は [multi-machine-state.md](multi-machine-state.md)

---

## まとめ: 自動化 pipeline 設計の checklist

新規自動化 script を書く前に以下を確認:

- [ ] データの単一ソースを決めた? (= 二重管理回避)
- [ ] schema 拡張は forward-only? (= 一括 backfill 避ける)
- [ ] judgment-required content に placeholder pattern を用意した? (= AI 初稿 + user edit)
- [ ] user input は regex validate? path traversal mitigation?
- [ ] 必須 field 欠落は explicit error?
- [ ] 過去 user 承認済出力で reproduce 検証した? (= validity 確認)
- [ ] yaml の自動 edit を避けて print reminder にした?
- [ ] **無人実行なら**: 自動 publish は推測ゼロの変換だけ? 導出不能 field は事前入力 (armed) or surface? (§7)
- [ ] **無人 commit なら**: clean∧ff-only-or-abort → build 検証 → 失敗 revert → commit → push retry を mechanize した? (§7)

### 関連 convention

- 既存 [convention-design-principles.md](../docs/convention-design-principles.md) §2 「ルールの重複を避ける」 は **規約** の単一ソース化、 本 convention §1 は **データ** の単一ソース化。 思想は同じ
- [scientific-computing.md](scientific-computing.md): 計算結果 artifact の保存規律 (= 似たテーマ、 個別 domain)
