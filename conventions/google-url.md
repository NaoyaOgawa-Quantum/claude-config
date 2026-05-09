# Google 系サービスの URL 書式

Gmail / Drive / Photos / Classroom / Calendar / Docs / Sheets / Slides 等の Google 系サービスで Claude がチャットや文書に URL を出力するときの規約。CLAUDE.md から参照: `~/Claude/claude-config/conventions/google-url.md`

## 核となる規則

**2 つの規律を併用する**:

1. **`/u/N/` 書式 (account slot index) を生成しない** — ブラウザの account 追加順依存で壊れる
2. **Account-sensitive な URL には `?authuser=<email>` を付ける** — ブラウザに複数 Google アカウントがログインしている場合、 stable ID だけでは active account 依存で壊れる (権限なし → 404 / 別 view が開く)

NG 例:

- `https://mail.google.com/mail/u/0/#inbox` ← `/u/N/` 違反
- `https://classroom.google.com/u/2/c/...` ← `/u/N/` 違反
- `https://drive.google.com/drive/u/1/...` ← `/u/N/` 違反
- `https://classroom.google.com/c/{classId}` ← stable ID だけ、 authuser= 抜け、 別 account active 時は 404
- `https://docs.google.com/document/d/{docId}/edit` ← 同上

OK 例 (stable ID + `?authuser=<email>` 併用):

- `https://classroom.google.com/c/{classId}?authuser=<email>`
- `https://docs.google.com/document/d/{docId}/edit?authuser=<email>`
- `https://mail.google.com/mail/u/?authuser=<email>#inbox`

## Why

### `/u/N/` を避ける理由

`/u/N/` の N は **ブラウザセッションでの Google アカウント追加順** に依存。

- user がアカウントを追加・削除すると N がずれる
- 別マシンで開くと N が違う
- 一度ログアウトして再ログインすると順序変更される

Claude が生成した `/u/N/` URL は、user の環境が変わった瞬間に壊れる link になる。「書いた時点では正しい」では不十分 — 後から読んだときに壊れている可能性が高い。

### `?authuser=<email>` を併記する理由

stable ID 形式 (`classroom.google.com/c/{id}` 等) は account 非依存に **見える** が、 ブラウザに複数の Google アカウントがログインしているときは active account の view で開く:

- 別 account が active で当該 ID への権限が無い → 404 / access denied
- 別 account が active で同 ID にも別 view (= 別 role) で参加している → 意図と違う view

`?authuser=<email>` を付ければブラウザが対象アカウントに切替えて開く (= 決定論的)。 single-account user でも明示する方が forward-compatible (後で multi-account になっても壊れない、 共著者・共同研究者に URL を渡したときも各自の `<email>` で開ける感覚的整合性)。

## How to apply

### (a) Stable identifier + `?authuser=<email>` を使う (推奨)

Google 系サービスは多くの場合、 account-independent な stable URL を持つ。 これに **`?authuser=<email>` を併記** する:

| サービス | Stable URL 形式 (with authuser=) |
|---|---|
| Gmail (thread) | *stable URL 不在*。 Thread ID / Draft ID / Message ID を提供して user navigation に任せる (次項) |
| Drive (file) | `https://drive.google.com/file/d/{fileId}/view?authuser=<email>` |
| Drive (folder) | `https://drive.google.com/drive/folders/{folderId}?authuser=<email>` |
| Docs / Sheets / Slides | `https://docs.google.com/document/d/{docId}/edit?authuser=<email>` (sheets / presentation も同) |
| Photos (album) | `https://photos.google.com/share/{shareId}?authuser=<email>` (共有 link がある場合) |
| Classroom | `https://classroom.google.com/c/{classId}?authuser=<email>` |
| Calendar (event) | `https://www.google.com/calendar/event?eid={eventId}&authuser=<email>` |
| Calendar (view) | `https://calendar.google.com/calendar/r?authuser=<email>` |
| Meet | `https://meet.google.com/{code}?authuser=<email>` |

### (b) Stable URL がない場合 — ID を渡して navigation を user に任せる

Gmail のように stable URL が存在しないケースでは、 **URL を構築せず、 ID だけを提供**する:

```
Thread ID: 19d3e72ae4005b23
Draft ID:  r-5529726991427467827
```

user は自分の Gmail (すでにログイン中) で navigation する。 `/u/N/` を推測するより正確で、 user の環境に依存しない。 root URL が必要なら `?authuser=<email>` 付きで:

```
https://mail.google.com/mail/u/?authuser=<email>#inbox
```

### (c) どうしても account-less root URL が必要なら

「Google サービス全般を開く」 系の説明的 URL は、 account slot を含まない root のみ書く:

- `https://mail.google.com/mail/`
- `https://drive.google.com/`
- `https://classroom.google.com/`

ブラウザは current active account で開く。 決定論性は無い。

## 例

**NG** (account-dependent、 壊れる):

```
Gmail lab thread を確認してください:
https://mail.google.com/mail/u/1/#all/19d3e72ae4005b23
```

**OK** (ID 提供、 navigation は user に任せる):

```
Gmail lab で thread 19d3e72ae4005b23 を確認してください。
(Gmail を開く → 適切な account に切替 → thread ID で検索または直接参照)
```

**NG** (stable ID のみ、 multi-account で active が違うと壊れる):

```
Classroom: https://classroom.google.com/c/{classId}
```

**OK** (stable ID + `?authuser=<email>`):

```
Classroom: https://classroom.google.com/c/{classId}?authuser=<email>
```

## 既存の具体例 (この規則が適用される箇所)

- `lectures/CLAUDE.md` の Classroom クラス一覧: stable URL `classroom.google.com/c/{ID}` を使用 (本規則の初出 context、 本ファイル新設の契機)。 ターン応答で URL を出すときは `?authuser=<email>` を併記する
- `odakin-prefs/user-profile.md` の「ブラウザでアクセス」: 2026-04-16 に `/u/1/` → `authuser=<email>` 形式に修正済み
- `claude-config/hooks/google-url-guard.sh`: PreToolUse hook (Edit / Write / MultiEdit / Bash) で **(A) `/u/N/` パターン** と **(B) account-sensitive な URL の authuser= 抜け** を検出して `permissionDecision=ask` で確認を仰ぐ。 setup.sh が ~/.claude/hooks/ に symlink を作成 + settings.json にマージ (2026-04-16 (A) 追加、 2026-05-09 (B) 追加 + claude-config 配下に移動)

## 失敗履歴

- **2026-04-16**: `/u/N/` パターンが 2 回再発。 規約と CLAUDE.md inline ルールが両方あったが Claude が読まず、 機械的ブロック (`/u/N/` 検出 hook) を導入
- **2026-05-09**: Classroom URL `https://classroom.google.com/c/{id}` を `?authuser=` 抜きで chat 出力。 active account 依存で壊れる risk を踏んでいた。 hook の検出範囲を「(B) account-sensitive な URL の authuser= 抜け」 まで拡張 + 本 convention に「stable ID だけでは不十分」 を明示 (本 commit)
