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
