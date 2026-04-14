# Identity-in-Config 規約

**対象**: 設定ファイル (`*.yaml` / `*.toml` / `*.json` / `.env` / 等) に埋め込まれる、実在する特定個人を指す identifier の取扱い。

## 問題: "PII-in-disguise"

下のような field は **application config のフォルトラインに紛れこんだ PII** で、email や phone number と同等の識別子として扱う必要がある。しかし field 名が innocent (timeout や retry_count と同クラス) のため、書き手の認識が起動しない。

| 形式 | プラットフォーム | 例 |
|---|---|---|
| `<@NNNNNNNNNNNNNNNNN>` | Discord (user mention) | `<@1234567890123456789>` |
| `<@&NNNNNNNNNNNNNNNNN>` | Discord (role mention) | `<@&9876543210987654321>` |
| `UXXXXXXXXXX` / `WXXXXXXXXXX` | Slack (user ID) | `U01A2B3C4D5` |
| `@user:server.tld` | Matrix | (既存 email regex で拾う) |
| `@user@instance.tld` | Mastodon / ActivityPub | (既存 email regex で拾う) |
| 数値のみ (int64) | Telegram / LINE chat ID | regex で拾えない — field 名から推測するしかない |

### なぜ危険か

Discord 数値 ID 単体の危険度は低いが、**実名・所属・役職・所属コミュニティと並列されると dox (doxxing) 素材価値が跳ね上がる**。public repo の profile / config / docs にこれらの情報が隣接して存在するのが最悪パターン。

加えて、これらの ID は一度 public に push されると:

- force-push で main から外しても、GitHub が orphan commit を SHA 直接アクセスで serve し続ける (自然 GC まで数日〜数ヶ月)
- 本人が ID を変更することは困難 (Discord は user ID 不変、Slack は workspace 固定)
- archive.org / fork / clone されていたら完全除去不能

## 対策: layer 3 + env var bridge パターン

odakin の 4 層アーキテクチャ (`docs/personal-layer.md`) に従って、identity-in-config は **layer 3 (collaborator registry)** を canonical source とし、public tool (layer 1) 側は **env 変数名のみ**を保持する:

```
┌─────────────────────────────────────────────────────────────────┐
│ layer 3 (private, git-crypt)                                    │
│   research-collab/collaborators.yaml                            │
│   - id: alice                                                   │
│     discord_id: "1234567890123456789"  ← 正本                  │
└──────────────────────────┬──────────────────────────────────────┘
                           │ odakin が手動 (or sync script で)
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│ runtime (local, gitignored)                                     │
│   <tool>/.env                                                   │
│   DISCORD_MENTION_ALICE=<@1234567890123456789>                  │
└──────────────────────────┬──────────────────────────────────────┘
                           │ os.environ[...] at load time
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│ layer 1 (public)                                                │
│   <tool>/profiles/alice/config.yaml                             │
│     mention_target_env: DISCORD_MENTION_ALICE   ← env 名のみ   │
└─────────────────────────────────────────────────────────────────┘
```

### 実装ルール

1. **public repo の config.yaml / profile には identity 数値 ID を直接書かない**。`mention_target_env: DISCORD_MENTION_<NAME>` のように env 変数**名**のみ保持する
2. **canonical source は layer 3**。`collaborators.yaml` (git-crypt) の `discord_id` field に置く (`conventions/collaborators.md` 参照)
3. **runtime 側は `.env` (gitignored)** が実値を保持。`load_dotenv()` 等で env に展開
4. **Cross-machine sync**: 新 Mac では `git-crypt unlock` 後に helper script (例: `tools/sync_mentions.py`) で `collaborators.yaml` → `.env` を再生成。Dropbox 暗号化 backup は不要 (layer 3 git-crypt が backup も兼ねる)
5. **Fail-soft**: env 未設定時に tool が crash しない設計にする。mention なしで送信 + warning log が無難

## 自動検出

- **`hooks/public-leak-guard.sh`** の tier A pattern `discord_mention` が `<@&?[0-9]{17,20}>` を検出 → PreToolUse で `permissionDecision=ask`
- **`scripts/audit-public-repos.sh`** が同 regex で既存 repo を遡及 scan → `### [tier-a/discord_mention]` section に report

## 他プラットフォームの扱い

現時点で regex 化しているのは Discord のみ。理由と今後の方針:

- **Slack (`UXXXXXXXXXX`)**: `\b[UW][A-Z0-9]{8,}\b` は false positive が多すぎる (大文字始まり英数識別子は一般的)。Slack 統合が実際に発生し leak 事例が出た時点で追加。それまでは convention doc でのみ規範化
- **Matrix / Mastodon**: `@user:server.tld` と `@user@instance` は既存 email regex で拾われる (tier-a/email に分類される)
- **Telegram / LINE chat ID**: 数値のみで regex 識別不能。field 名ベースで検出するには lint 層が必要、overengineering につき見送り
- **GitHub user ID (数値)**: 公開情報、PII 扱いしない

## 変更履歴

- 2026-04-14 作成。`arxiv-digest` の takeda / ogawa / onda profile で Discord 数値 ID が public config.yaml に直書きされていた leak を根本原因まで遡った結果として、identity-in-config カテゴリを独立規約として分離。事例記録は private layer の `odakin-prefs/leak-incidents.md` 2026-04-14 entry (ε + β 類型、force-push 修正)
