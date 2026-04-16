# Google 系サービスの URL 書式

Gmail / Drive / Photos / Classroom / Calendar / Docs / Sheets / Slides 等の Google 系サービスで Claude がチャットや文書に URL を出力するときの規約。CLAUDE.md から参照: `~/Claude/claude-config/conventions/google-url.md`

## 核となる規則

**`/u/N/` 書式 (account slot index) を生成しない**。

- `https://mail.google.com/mail/u/0/#inbox` ← NG
- `https://classroom.google.com/u/2/c/...`  ← NG
- `https://drive.google.com/drive/u/1/...`  ← NG

## Why

`/u/N/` の N は **ブラウザセッションでの Google アカウント追加順** に依存。

- user がアカウントを追加・削除すると N がずれる
- 別マシンで開くと N が違う
- 一度ログアウトして再ログインすると順序変更される

従って Claude が生成した `/u/N/` URL は、user の環境が変わった瞬間に壊れる link になる。「書いた時点では正しい」では不十分 — 後から読んだときに壊れている可能性が高い。

## How to apply

### (a) Stable identifier を使う

Google 系サービスは多くの場合、account-independent な stable URL を持つ:

| サービス | Stable URL 形式 |
|---|---|
| Gmail (thread) | *stable URL 不在*。Thread ID / Draft ID / Message ID を提供して user navigation に任せる (次項) |
| Drive (file) | `https://drive.google.com/file/d/{fileId}/view` (または `/edit`) |
| Docs / Sheets / Slides | `https://docs.google.com/document/d/{docId}/edit` (同様に sheets / presentation) |
| Photos (album) | `https://photos.google.com/share/{shareId}` (共有 link がある場合) |
| Classroom | `https://classroom.google.com/c/{classId}` |
| Calendar (event) | `https://www.google.com/calendar/event?eid={eventId}` |

### (b) Stable URL がない場合 — ID を渡して navigation を user に任せる

Gmail のように stable URL が存在しないケースでは、**URL を構築せず、ID だけを提供**する:

```
Thread ID: 19d3e72ae4005b23
Draft ID:  r-5529726991427467827
```

user は自分の Gmail (すでにログイン中) で navigation する。`/u/N/` を推測するより正確で、user の環境に依存しない。

### (c) どうしても root URL が必要なら

説明用に root URL が必要な場合 (例: 「Gmail を開いてください」)、account slot を含まない root のみ書く:

- `https://mail.google.com/mail/`
- `https://drive.google.com/`
- `https://classroom.google.com/`

ブラウザは current active account で開く。

## 例

**NG** (account-dependent、壊れる):

```
Gmail lab thread を確認してください:
https://mail.google.com/mail/u/1/#all/19d3e72ae4005b23
```

**OK** (ID 提供、navigation は user に任せる):

```
Gmail lab で thread 19d3e72ae4005b23 を確認してください。
(Gmail を開く → 適切な account に切替 → thread ID で検索または直接参照)
```

**OK** (stable URL 利用):

```
Classroom 2026 量子力学: https://classroom.google.com/c/ODU5MTM4NTYxMjg5
```

## 既存の具体例 (この規則が適用される箇所)

- `lectures/CLAUDE.md` の Classroom クラス一覧: stable URL `classroom.google.com/c/{ID}` を使用 (本規則の初出 context、本ファイル新設の契機)
- `odakin-prefs/user-profile.md` の「ブラウザでアクセス: `/mail/u/1/`」: これは odakin 本人がブラウザで開く用の meta 情報であって、Claude が生成する URL の規範ではない。混同しない
