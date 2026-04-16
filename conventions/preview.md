# プレビュー・テスト URL の出力ルール

ユーザーに動作確認・プレビューを依頼するときは、**毎回 URL を併記**すること。

## 対象

- `preview_start` (Claude Preview MCP) で起動したサーバー
- `python3 -m http.server` / `npm run dev` / `vite` / `next dev` 等、あらゆる方法で起動したローカルサーバー
- staging / production / preview deployment へのリンク (Vercel, Netlify, GitHub Pages 等)
- ローカルファイル直接 (`file:///path/to/index.html`) を開かせる場合もパスを書く

## ルール

- 「テストしてください」「ハードリロードしてください」「動作確認お願いします」「見え方どうですか?」など、ユーザーが評価アクションを取る依頼を含む応答では、**そのターン内で URL を毎回明示**する
- preview が動いている間は、関連する応答ごとに URL を再掲する。コード変更・HMR 反映報告・パラメータ調整の確認など、preview を触りうる全ターンが対象
- 「さっきの URL で…」「先程のページを…」のような遡及参照を強要しない

## Why

ユーザーは複数ターンの応答をスクロールで追わずに、その場でリンクを踏みたい。URL を毎回書く負担より、ユーザーがスクロールバックする摩擦のほうが大きい。

## How to apply

評価依頼を含むあらゆる応答で URL をその応答内に書く。「動作確認お願いします」「リロードしてください」だけ書いて URL を出さないのは NG。

## 例

✗ NG: 「修正しました。ブラウザでハードリロードしてください」
✓ OK: 「修正しました。**http://localhost:8742/index.html** をハードリロード (Cmd+Shift+R) してください」

✗ NG: 「デプロイ完了。ステージングで確認お願いします」
✓ OK: 「デプロイ完了。https://app-staging.example.com/foo で確認お願いします」

## Deploy 前のユーザー確認を省かない

視覚的・動作的に観察可能な変更 (UI, レンダリング, ゲーム挙動, 画面遷移等) は、Claude が `preview_screenshot` や snapshot で自己確認しただけで **そのまま push・deploy に進まない**。**ユーザーにローカル URL を提示して OK を得てから deploy すること**。

**Why:** Claude が見た screenshot (headless browser の 1 枚) とユーザーが自分のブラウザで見た実際の表示は別物。ジグザグ・色調・動きの違和感は screenshot では拾えず、ユーザーが実機で見て初めて分かる。deploy まで行ってしまうと public キャッシュ反映待ちが挟まり、修正サイクルが大幅に遅くなる (GitHub Pages・Cloudflare Pages 等)。

**How to apply:**

1. ローカル dev server を Bash バックグラウンドで起動 (`run_in_background: true`)
2. URL をリンクでユーザーに提示 (本ファイル上部「ルール」節のとおり毎回明示)
3. ユーザーが自分のブラウザで確認して OK/NG を返すまで待つ
4. OK → commit + push + deploy、NG → 修正して同じループ (HMR で dev server は継続、commit なしで反復可能)

**preview_start vs `pnpm dev` バックグラウンド**: preview_start は Claude の確認用 (preview_* ツールが使える)、`pnpm dev` の Bash バックグラウンドはユーザー共有用 (Claude の preview ブラウザが PeerJS ID 等を奪わない)。プロジェクトによっては同時に両方立てる (別ポート)、または preview_start を使わず `pnpm dev` だけで済ませる運用もあり。

**例外**: build / lint / typecheck だけで完結する変更 (観察不能なリファクタ・ドキュメント修正等) はこの手順不要。
