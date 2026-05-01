# discord-bot: Discord Bot を運用するときの規律

Bot を Discord API 経由で動かす場合の一般則。具体的な server / channel / Bot ID は個人層 (private リポ) に置き、本ファイルには generic pattern のみ。

## 権限ポリシー: Token 漏洩時の被害想定で決める

Bot に付ける channel-level / server-level 権限は「Token が漏れた時にどこまで被害が広がるか」を逆算して最小化する。以下は **「中立 (Allow しない、Deny もしない、= グレー)」がデフォ推奨**:

| 権限 | 中立にする理由 |
|---|---|
| Administrator | 絶対 NG (= 全権限相当) |
| Manage Channel | Token 漏洩時に channel 削除が可能 |
| Manage Permissions / Manage Roles | 他人の権限改変が可能 |
| Manage Webhooks | 外部にデータ流出経路を作れる |
| Manage Messages | 他人のメッセージ削除が可能 |
| Manage Threads | 他人のスレッド削除が可能 |
| Mention @everyone, @here, all roles | annoyance 源、本当に必要になったら個別追加 |
| Send TTS Messages | bot 用途で意味なし、ノイズ源 |

通常の posting bot に必要十分な権限セット (これらを Allow):

- 読み取り: View Channel, Read Message History
- 投稿: Send Messages, Embed Links, Attach Files, Send Voice Messages, Create Polls, Pin Messages
- インタラクション: Add Reactions, Use External Emojis, Use External Stickers, Use Application Commands, Use Embedded Activities, Use External Apps
- スレッド: Create Public Threads, Create Private Threads, Send Messages in Threads
- メンバーシップ: Create Invite (任意)

## Private channel への Bot 追加手順

`@everyone` の View Channel が deny された private channel では、server-level role による View Channel allow も override される。Bot を入れる手順:

1. **Bot user 自身、または Bot 用 role** を channel の「アクセス可」リスト (permission overwrite の allow 側) に追加
2. これで View Channel が channel-level で allow され、Read Message History 等の他権限は server-level role から継承される
3. 詳細権限 (Send Messages, Pin, Polls など) を追加で個別に Allow したい場合は、追加した role/member の詳細 toggle 画面で個別 ON

### Bot 自身が UI 操作の代行をできない理由

Bot が channel の permission overwrite を API 経由で変更するには `Manage Roles` 権限が必要。これを持たない bot は **自分自身に対する allow を API で追加できない** → server admin (人間) が UI で 1 度だけ操作する必要がある。これを最初に踏まえずに「API で全自動」と思い込むと、最後の 1 ステップで詰まる。

## 複数 channel から data を fetch するときの error handling

複数 channel を巡回する fetcher は **per-channel error を non-fatal に**。1 channel の権限欠如 (`Missing Access`) で全体を kill すると、他の正常 channel の data まで止まってしまう (= 1 channel の問題が全 channel の data 鮮度を巻き込む)。

```python
def fetch_channel(channel_id, name):
    # ...
    if not isinstance(msgs, list):
        if first_call:
            print(f'ERROR: {name}: ...', file=sys.stderr)
            return None  # ← sys.exit(1) ではなく None
        break
    # ...

failed = []
for name, cid in channels.items():
    msgs = fetch_channel(cid, name)
    if msgs is None:
        failed.append(name); continue
    # ... write to file ...

if failed:
    print(f'NOTE: failed channels skipped: {", ".join(failed)}', file=sys.stderr)
    sys.exit(1)  # ← 末尾で non-zero exit して UI failure を維持
```

GitHub Actions の workflow 側で **後続 step に `if: always()`** を付け、partial failure でも commit/push を走らせる:

```yaml
- name: Commit if changed
  if: always()  # partial-failure でも successful channels は commit
  run: |
    git add ... && (git diff --cached --quiet || (git commit ... && git push))
```

これで「UI failure を見て修復する signal を保つ」+「正常 channel の data は反映される」を両立。1 channel が permission 系で死んでいても他の data 鮮度は守られる。

## Bot Token の取り扱い

- canonical 配置: `~/.secrets/<bot>-token` の形 (チーム / project 単位、`secrets-config` 規約と整合)
- リポ内 backup を持つ場合は **git-crypt 暗号化必須**。平文 commit は禁止
- chat / public リポ / メール本文への literal 貼付は禁止
- GitHub Actions では `${{ secrets.<NAME> }}` 経由で env var に注入し、log で `***` mask されることを確認 (`echo $TOKEN` のような直接出力をしない)

## ネットワーク制約: 一部の組織 NW から Discord API は届かない

職場 NW 等から Discord API (`discord.com/api/v10/...`) は **Cloudflare 1010 でブロック** されることがある (組織のセキュリティポリシー次第、当該 NW の egress filtering)。Python `urllib` も同様にブロックされうる。

回避: Bot operations は GitHub Actions / 自宅環境から実行する設計に倒す。組織 NW で API 動作を当てにしない (動かないのが default と考える)。

## 関連

- `identity-in-config.md`: Discord user ID 等を config に書くときの PII レイヤ判定
- `mcp.md`: MCP 経由の Discord 連携を組む場合 (現状は Discord 用の標準 MCP がないため Bot Token + curl/SDK の直接 API call が一般的)
