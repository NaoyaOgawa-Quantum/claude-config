# Web ツール (WebSearch / WebFetch) の信頼性 caveat

WebSearch / WebFetch は便利だが post-processing 由来の落とし穴があり、**事実確認用途では補助検証が必須**。

## WebSearch の summary は hallucinate する

WebSearch の result block 末尾に付く自然言語 summary は検索エンジンが推測した情報を含み、リンク先 source に存在しない値を捏造することがある。**事実値 (メールアドレス・電話番号・URL・固有名) は summary だけで採用してはいけない**。

### How to apply

- メールアドレス・電話番号・URL のような事実値は、リンクされた source ページ (公式サイト・PDF press release 等) を WebFetch / curl で直接確認してから採用する
- 複数の異なる値が出てきたら最新の公式 source を優先
- ヒットしたリンクのうち最も authoritative なもの (組織の公式 domain 等) を優先

### 典型パターン

ある組織の窓口メールアドレスを WebSearch で取得しようとすると、summary に「`<role>@<domain-A>`」 のような値が返ってくることがある。実際に source を確認すると、PDF (古い文書) には「`<role>@<domain-B>`」、現行公式 contact ページには「`<role>@<domain-C>`」 と書いてあって、summary に出た `<domain-A>` 版はどちらにも存在しない hallucination だった、というケース。検索エンジンが「`<role>` + 組織ドメインの慣用 prefix」 から推測しただけ。

## WebFetch は `<head>` 内 meta タグ・JSON-LD を落とす

WebFetch は HTML → markdown 変換 + 内部要約モデル処理を経るため、`<head>` 内の `<meta>` `<link>` `<script type="application/ld+json">` 等は実質的に削られる。「**Open Graph / Twitter Card / canonical / verification meta / JSON-LD / hreflang を確認したい**」 用途では WebFetch は使えない。

### How to apply

- meta / OG / JSON-LD / canonical / hreflang / verification token の検証は **`curl + sed` で生 HTML を取得して grep** する
- 例: `curl -sS https://example.com/ | sed -n '/<head>/,/<\/head>/p'`
- JSON-LD が body 内に出力されているケースもあるので、見つからなければ `curl ... | grep -A20 '"@type"'` で全文 grep
- WebFetch は記事本文抽出・要約・自然言語回答用途には適切 (= ナラティブ系コンテンツ向け)

### 典型パターン

WebFetch に「`<head>` 内の meta タグを抽出して」 と prompt しても「<head> セクションは提供されていません」 と返答するケースがある。post-processing で削られているため。代わりに `curl + sed` で head を取得して verification meta / Open Graph / JSON-LD を直接確認する。SEO 検証 (Search Console verification token / OG image / Event JSON-LD 等の live 確認) で典型的に発生する。

## ロックイン済 web app からのテーブル data 取得は scrape より export を優先

認証済 web UI (broker / CRM / e-commerce / analytics dashboard 等) のテーブル view から data を取得するときは、**scrape を始める前に「CSV ダウンロード」 / "Export" / "Excel" ボタンの有無を確認する**。ある場合は scrape より遥かに早く正確で、ページ実装の癖に破綻しない。

### How to apply

- 認証済 web UI でテーブル data を見ている時、ページ上に "CSVダウンロード" / "Export" / "Download CSV" / "Excel" / "ダウンロード" 等のボタンが無いか先に探す
- 見つかった場合: それを使う。ファイルとして保存され、機械可読、virtual-scroll や lazy-load の影響を受けない
- 無い場合のみ scrape (DOM 抽出 / paste 経由) に移る
- export 結果のスコープは要確認 — 多くのアプリは「現在のフィルタ」 を反映するが、一部は**全 data** を出す (= フィルタした表示より広い)。1 度ダウンロードして件数を確認するだけで判別できる
- export を見落としたまま scrape に着手すると、後から「CSV あった」 で全 work がやり直しになる。**最初の 30 秒で UI を全体スキャンしてから方針を決める** のが結果的に速い

### 典型パターン

paste-and-transcribe で rendered DOM を写す方針を取った後で問題が複合する: lazy-load で見えていない行が rendered DOM に存在しない、virtual-scroll 領域外の行は paste できない、複数 dump 間で重複・脱漏が発生する、別フィルタの dump 同士で混乱、行のセル順序がブラウザ render 設定に依存して微妙にズレる、等。CSV export は raw 値ベースで一発取得できるためこれらが構造的に発生しない。

一方、UI badge ("NEW" / "保有中" / "在庫切れ" 等) は CSV に含まれないことが多い。**badge を本当に必要とする用途**では、CSV export を canonical source にし、DOM scrape を annotation overlay として **両方取る hybrid アプローチ**を採る (CSV で 95% の事実、DOM で 5% の UI 注釈)。

---

## 学術論文 PDF の WebFetch 限界と迂回路

学術文献の URL を素朴に WebFetch する典型失敗パターンと迂回路。

| ソース | 挙動 | 迂回路 |
|---|---|---|
| 古い scan PDF（例: 日本気象学会「天気」 1990 年代以前、CCITT FAX 圧縮の bitmap） | 本文テキスト抽出不可（画像 PDF） | CiNii / AGU 等の abstract page、後継論文の citation 中の要約 |
| Wiley Online Library / ResearchGate / Elsevier | 403 Forbidden | arXiv preprint、著者個人ページ、ADS abstract |
| ADS (`ui.adsabs.harvard.edu/abs/...`) | abstract 取得可 | 引用関係・要旨確認に有効 |
| arXiv (`arxiv.org/abs/...`) | フルテキスト OK | 物理・数学・CS 系の第一選択 |
| CiNii (`ci.nii.ac.jp/naid/...`) | 旧 `naid` URL は `cir.nii.ac.jp/crid/...` に 301 redirect | redirect 先で再 WebFetch |

### How to apply

- arXiv ID があれば arXiv → なければ ADS abstract → 後継論文の citation 経由、の順で確認する
- 古い和文論文は本文 PDF が画像形式なら諦めて、引用している後継論文の本文中要約を信用する
- 商用 publisher の paywall ページは内容が取れないので時間を浪費しない
