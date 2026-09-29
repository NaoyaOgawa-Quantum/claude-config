#!/usr/bin/env python3
"""
drive-upload-share.py — ローカル file を Google Drive に upload し、 共有して URL を返す (engine)。

Google Drive にローカル file を upload し、 指定 user (email) / ドメインに権限を付与し、 共有 URL を返す。
同じ file を毎回新しく上げる重複を避けるため `--reuse-by-name` で同名 file を探し、 あれば上書きする。

使い方 (engine を直接):
    python3 drive-upload-share.py --credentials <token.json> --client <oauth-client.json> \\
        --file <local-path> [...] \\
        [--share-with <email> ...] [--share-domain <domain> ...] \\
        [--role viewer|commenter|editor] [--folder-id <id> | --make-folder <NAME>] \\
        [--reuse-by-name] [--overwrite-others] [--as-google-doc] [--notify] \\
        [--account-label <表示名>]
    python3 drive-upload-share.py --selftest

    <token.json> = refresh_token と scope を持つ OAuth の token (authorized user の形)。
    <oauth-client.json> = OAuth client (installed / web)。
    owner ごとの account と token の在り処は下層の shim が渡す (engine は account 名も path も持たない)。

- `--as-google-doc` = docx / html / txt を Google ドキュメント (native) に変換して置く (共有相手がブラウザで編集できる)。
  Drive 上の名前は拡張子なし。
- `--reuse-by-name` の上書きは、 最後に編集したのが自分でなければ止まる (共有相手の編集を消さない。 native の文書には
  md5Checksum が無いので最後の編集者で見る)。 強行 = `--overwrite-others`。
- `--make-folder` = フォルダを作って (同名があれば使い回す) その中に上げ、 共有はフォルダに付ける (中の file は継承)。
  ⚠️ 順序: 権限を付けてから upload する (逆順だと中の file への継承が非同期で、 直後は他者から見えない = 実測)。
- `--share-domain` はリンク限定 (allowFileDiscovery=False)。 ⚠️ 同じ組織でも subdomain ごとに別ドメイン扱いになる
  ことがある (親のドメインへの共有が子に届かない = 実測) → 見せたい subdomain を別々に付ける。
- `--notify` が無ければ共有の通知メールは送らない。

scope: `drive.file` (= この OAuth client で作った file だけを書ける) + `drive.readonly` (= 同名検索用)。
出力 (stdout): 完了の見出し・account・file ごとの名前と URL・付けた権限・コピー用 URL。
規約 = conventions/google-classroom-api.md (#replace-attachment-in-place = 添付の差し替え / native の文書の上書き前の確認)、
層の分け方 = conventions/script-layer-placement.md。
"""
from __future__ import annotations

import argparse
import json
import mimetypes
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore", category=FutureWarning)

try:
    from googleapiclient.errors import HttpError
except ImportError:  # pragma: no cover - selftest は fake だけで回る
    class HttpError(Exception):  # type: ignore[no-redef]
        reason = ""

FOLDER_MIME = "application/vnd.google-apps.folder"
GDOC_MIME = "application/vnd.google-apps.document"

ROLE_MAP = {
    "viewer": "reader",
    "reader": "reader",
    "commenter": "commenter",
    "editor": "writer",
    "writer": "writer",
}


def build_service_from(cred_path, client_path, setup_hint: str = ""):
    """token file と OAuth client file から Drive v3 の service を作る (token は書き戻さない)。"""
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    cred_path = Path(cred_path)
    if not cred_path.exists():
        sys.exit(f"❌ {cred_path} が存在しません。" + (f" setup 手順:\n{setup_hint}" if setup_hint else ""))
    cred = json.load(open(cred_path))
    oauth = json.load(open(client_path))
    inst = oauth.get("installed") or oauth.get("web") or {}
    creds = Credentials(
        token=cred.get("access_token"),
        refresh_token=cred.get("refresh_token"),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=inst.get("client_id"),
        client_secret=inst.get("client_secret"),
        scopes=cred.get("scope", "").split(" "),
    )
    if not creds.valid and creds.refresh_token:
        creds.refresh(Request())
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def find_by_name(drive, name: str, folder_id: str | None, mime: str | None = None) -> dict | None:
    """同名 file を find (= app-created に限定、 drive.file scope の制約)。
    folder_id 指定があれば、 その folder 内に絞る。 mime 指定があればその種類に絞る。"""
    q_parts = [f"name = '{name}'", "trashed = false"]
    if mime:
        q_parts.append(f"mimeType = '{mime}'")
    if folder_id:
        q_parts.append(f"'{folder_id}' in parents")
    q = " and ".join(q_parts)
    try:
        resp = drive.files().list(
            q=q,
            fields="files(id, name, mimeType, modifiedTime, webViewLink, lastModifyingUser(me, emailAddress))",
            pageSize=10,
        ).execute()
    except HttpError:
        return None
    files = resp.get("files", []) or []
    return files[0] if files else None


def ensure_folder(drive, name: str) -> dict:
    """app-created の同名 folder を reuse、 なければ My Drive 直下に作成。"""
    q = f"name = '{name}' and mimeType = '{FOLDER_MIME}' and trashed = false"
    try:
        resp = drive.files().list(
            q=q, fields="files(id, name, webViewLink)", pageSize=5).execute()
        files = resp.get("files", []) or []
        if files:
            print(f"♻️  既存 folder を reuse: {files[0]['id']}", file=sys.stderr)
            return files[0]
    except HttpError:
        pass
    created = drive.files().create(
        body={"name": name, "mimeType": FOLDER_MIME},
        fields="id, name, webViewLink",
    ).execute()
    print(f"📁 新規 folder 作成: {created['id']}", file=sys.stderr)
    return created


def _media(local_path: Path, mime: str):
    from googleapiclient.http import MediaFileUpload
    return MediaFileUpload(str(local_path), mimetype=mime, resumable=False)


def upload_file(drive, local_path: Path, folder_id: str | None,
                reuse_by_name: bool = False, as_google_doc: bool = False,
                overwrite_others: bool = False, media_factory=None) -> dict:
    """upload (or update if reuse_by_name)。 returns file resource。

    as_google_doc = docx / html / txt を Google ドキュメント (native) に変換して置く (Drive 上の名前は拡張子なし)。
    上書き (reuse_by_name) は、 最後に編集したのが自分でなければ止める = 共有相手の編集を消さない
    (native の文書には md5Checksum が無いので、 最後に編集した人で見る)。 overwrite_others で強行。"""
    name = local_path.stem if as_google_doc else local_path.name
    mime = mimetypes.guess_type(str(local_path))[0] or "application/octet-stream"
    media = (media_factory or _media)(local_path, mime)

    if reuse_by_name:
        existing = find_by_name(drive, name, folder_id, GDOC_MIME if as_google_doc else None)
        if existing:
            who = existing.get("lastModifyingUser") or {}
            if not who.get("me", True) and not overwrite_others:
                sys.exit(f"❌ 上書きしない: 最後に編集したのは {who.get('emailAddress', '別の人')} "
                         f"({existing.get('modifiedTime')})。 その人の編集が消える。 "
                         "強行するなら --overwrite-others")
            # update content (= overwrite)
            updated = drive.files().update(
                fileId=existing["id"],
                media_body=media,
                fields="id, name, mimeType, modifiedTime, webViewLink",
            ).execute()
            print(f"♻️  既存 file を update: {updated['id']}", file=sys.stderr)
            return updated

    body = {"name": name}
    if as_google_doc:
        body["mimeType"] = GDOC_MIME
    if folder_id:
        body["parents"] = [folder_id]
    created = drive.files().create(
        body=body,
        media_body=media,
        fields="id, name, mimeType, modifiedTime, webViewLink",
    ).execute()
    print(f"✨ 新規 upload: {created['id']}", file=sys.stderr)
    return created


def grant_permission(drive, file_id: str, email: str, role: str,
                     send_notification: bool = False) -> dict:
    """指定 email に role 付与。"""
    body = {
        "type": "user",
        "role": role,  # "reader" (= viewer) / "commenter" / "writer"
        "emailAddress": email,
    }
    return drive.permissions().create(
        fileId=file_id,
        body=body,
        sendNotificationEmail=send_notification,
        fields="id, type, role, emailAddress",
    ).execute()


def grant_domain_permission(drive, file_id: str, domain: str, role: str) -> dict:
    """指定ドメインに **リンク限定** の role を付与 (= type:domain、 allowFileDiscovery=False)。
    当該ドメインの user が URL を持っていれば閲覧可、 検索 / 一覧には出ない (= 外部・公開ではない)。
    ⚠️ 同じ組織でも subdomain ごとに別ドメイン扱いのことがある (実測) = 見せたい subdomain を別々に付ける。"""
    body = {
        "type": "domain",
        "role": role,
        "domain": domain,
        "allowFileDiscovery": False,  # リンク限定 (= 検索で発見されない)
    }
    return drive.permissions().create(
        fileId=file_id,
        body=body,
        sendNotificationEmail=False,
        fields="id, type, role, domain",
    ).execute()


def build_parser(add_account_args=None, description: str | None = None) -> argparse.ArgumentParser:
    """CLI の parser。 add_account_args(parser) を渡すと、 認証の引数はその関数が足す (下層の shim 用)。
    渡さなければ engine 自身の --credentials / --client / --account-label を足す。"""
    parser = argparse.ArgumentParser(description=description or __doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--file", required=True, nargs="+",
                        help="local file path(s) to upload (複数可)")
    parser.add_argument("--make-folder", metavar="NAME",
                        help="Drive にフォルダ NAME を作成 (同名 app-created folder あれば reuse) し、 "
                             "file をその中に upload。 共有 (--share-with / --share-domain) は "
                             "**フォルダに付与** (= 中の file は継承)、 返す URL もフォルダ URL。 "
                             "委員会資料等の複数 file 一括共有向け。 --folder-id とは排他")
    parser.add_argument("--share-with", nargs="+", default=[],
                        help="email(s) に個別共有 (= type:user)。 --share-domain と併用可。 "
                             "両方省略なら非共有 (= owner だけ、 後で Drive UI で共有)")
    parser.add_argument("--share-domain", nargs="+", default=[], metavar="DOMAIN",
                        help="ドメインにリンク限定共有 (= type:domain、 allowFileDiscovery=False = "
                             "リンクを持つ当該ドメインの人のみ閲覧、 検索に出ない)。 ⚠️ subdomain ごとに "
                             "別ドメイン扱いのことがある = 見せたい subdomain を並べる")
    parser.add_argument("--role", default="viewer",
                        choices=list(ROLE_MAP.keys()),
                        help="permission role (default: viewer = read-only)")
    parser.add_argument("--folder-id", help="Drive folder ID to place file in (optional)")
    parser.add_argument("--reuse-by-name", action="store_true",
                        help="同名 file あれば update (= 上書き)。 default = 毎回新規 upload")
    parser.add_argument("--as-google-doc", action="store_true",
                        help="docx / html / txt を Google ドキュメント (native) に変換して置く "
                             "(共有相手がブラウザでそのまま編集できる。 Drive 上の名前は拡張子なし)")
    parser.add_argument("--overwrite-others", action="store_true",
                        help="--reuse-by-name の上書きで、 最後に編集したのが自分でなくても上書きする "
                             "(既定は止める = 共有相手の編集を消さない)")
    parser.add_argument("--notify", action="store_true",
                        help="送信先 email に通知メールを送る (default: silent)")
    if add_account_args:
        add_account_args(parser)
    else:
        parser.add_argument("--credentials", required=True, help="OAuth の token file (refresh_token つき)")
        parser.add_argument("--client", required=True, help="OAuth client file (installed / web)")
        parser.add_argument("--account-label", default="(token の account)",
                            help="出力の account 行に出す表示名")
    return parser


def run(args, drive, account_label: str, media_factory=None) -> None:
    """parse 済みの args で upload + 共有をして結果を出す (drive = Drive v3 service か同じ形の fake)。"""
    if args.make_folder and args.folder_id:
        sys.exit("❌ --make-folder と --folder-id は排他")

    local_paths = [Path(f).expanduser().resolve() for f in args.file]
    missing = [p for p in local_paths if not p.exists()]
    if missing:
        sys.exit("❌ file not found: " + ", ".join(str(p) for p in missing))

    role = ROLE_MAP[args.role]

    # upload 先 + 共有 target の決定
    folder = None
    if args.make_folder:
        folder = ensure_folder(drive, args.make_folder)
        folder_id = folder["id"]
    else:
        folder_id = args.folder_id

    perms, domain_perms = [], []

    def apply_shares(target_id: str):
        for email in args.share_with:
            try:
                p = grant_permission(drive, target_id, email, role, args.notify)
                perms.append((email, p.get("role"), "✓"))
            except HttpError as e:
                perms.append((email, role, f"❌ {getattr(e, 'reason', '') or str(e)}"))
        for dom in args.share_domain:
            try:
                p = grant_domain_permission(drive, target_id, dom, role)
                domain_perms.append((dom, p.get("role"), "✓"))
            except HttpError as e:
                domain_perms.append((dom, role, f"❌ {getattr(e, 'reason', '') or str(e)}"))

    # ⚠️ 順序が重要 (実測): folder 共有は **権限付与 → upload** の順だと中の file へ即時継承、
    # 逆順 (upload → 権限) だと伝播が非同期 (~5s) で直後は他者から不可視。
    if folder:
        apply_shares(folder["id"])
    files = [upload_file(drive, p, folder_id, args.reuse_by_name, args.as_google_doc,
                         args.overwrite_others, media_factory) for p in local_paths]
    if not folder:
        for file in files:
            apply_shares(file["id"])

    print(f"\n=== upload + share 完了 ===")
    print(f"account     : {account_label}")
    if folder:
        folder_url = folder.get("webViewLink",
                                f"https://drive.google.com/drive/folders/{folder['id']}")
        print(f"folder      : {folder.get('name')} ({folder['id']})")
        print(f"folderLink  : {folder_url}")
    for file in files:
        url = file.get("webViewLink", f"https://drive.google.com/file/d/{file['id']}/view")
        print(f"  - {file.get('name')}  {url}")
    if perms:
        print(f"\nuser permissions ({len(perms)} 件):")
        for email, r, status in perms:
            print(f"  {status} {email:40s} role={r}")
    if domain_perms:
        tgt = "folder" if folder else "file"
        print(f"\ndomain permissions ({len(domain_perms)} 件、 link-restricted、 target={tgt}):")
        for dom, r, status in domain_perms:
            print(f"  {status} {dom:30s} role={r}")
    if not perms and not domain_perms:
        print(f"\n(共有なし = owner のみ。 共有は --share-with / --share-domain or Drive UI で)")
    print(f"\nコピー用 URL (= chat / mail 用):")
    if folder:
        print(f"  {folder_url}")
    else:
        for file in files:
            print(f"  {file.get('webViewLink', 'https://drive.google.com/file/d/' + file['id'] + '/view')}")


def main(argv=None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    drive = build_service_from(args.credentials, args.client)
    run(args, drive, args.account_label)


# ---------------------------------------------------------------- selftest (fake の Drive だけで回る)

class _Req:
    def __init__(self, fn):
        self.fn = fn

    def execute(self):
        return self.fn()


class _FakeDrive:
    """files().list/create/update と permissions().create を記録する最小の fake。"""

    def __init__(self, existing=None):
        self.existing = existing or []   # list の結果として返す file
        self.calls = []
        self._n = 0

    def _id(self):
        self._n += 1
        return f"id{self._n}"

    def files(self):
        outer = self

        class F:
            def list(self, q, fields, pageSize):
                outer.calls.append(("list", q))
                return _Req(lambda: {"files": list(outer.existing)})

            def create(self, body, fields, media_body=None):
                outer.calls.append(("create", dict(body)))
                return _Req(lambda: {"id": outer._id(), "name": body["name"],
                                     "mimeType": body.get("mimeType"), "webViewLink": "https://example.invalid/f"})

            def update(self, fileId, media_body, fields):
                outer.calls.append(("update", fileId))
                return _Req(lambda: {"id": fileId, "name": "x", "webViewLink": "https://example.invalid/u"})
        return F()

    def permissions(self):
        outer = self

        class P:
            def create(self, fileId, body, sendNotificationEmail, fields):
                outer.calls.append(("perm", fileId, body.get("emailAddress") or body.get("domain"),
                                    body["role"], sendNotificationEmail))
                return _Req(lambda: {"id": "p", "role": body["role"]})
        return P()


def _selftest() -> int:
    import contextlib
    import io
    import tempfile
    ok = True

    def check(label, cond):
        nonlocal ok
        print(f"  {'✅' if cond else '❌'} {label}")
        ok = ok and bool(cond)

    d = Path(tempfile.mkdtemp())
    doc = d / "matome.docx"
    doc.write_bytes(b"fake")
    media = lambda p, m: None  # noqa: E731 - fake

    def quiet(fn, *a, **k):
        with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
            return fn(*a, **k)

    # 1. --as-google-doc の新規 = native の種類で、 名前は拡張子なし
    fd = _FakeDrive()
    quiet(upload_file, fd, doc, None, False, True, False, media)
    body = [c[1] for c in fd.calls if c[0] == "create"][0]
    check("as_google_doc: mimeType = Google ドキュメント", body.get("mimeType") == GDOC_MIME)
    check("as_google_doc: 名前は拡張子なし", body.get("name") == "matome")

    # 2. 上書き: 最後の編集者が自分でなければ止まる
    other = {"id": "E1", "lastModifyingUser": {"me": False, "emailAddress": "coteacher@example.org"}}
    fd = _FakeDrive([other])
    stopped = False
    try:
        quiet(upload_file, fd, doc, None, True, True, False, media)
    except SystemExit:
        stopped = True
    check("上書きの検査: 他人が最後に編集 → 止まる", stopped and not any(c[0] == "update" for c in fd.calls))
    fd = _FakeDrive([other])
    quiet(upload_file, fd, doc, None, True, True, True, media)
    check("上書きの検査: --overwrite-others なら上書き", any(c == ("update", "E1") for c in fd.calls))
    fd = _FakeDrive([{"id": "E2", "lastModifyingUser": {"me": True}}])
    quiet(upload_file, fd, doc, None, True, True, False, media)
    check("上書きの検査: 自分が最後なら上書き", any(c == ("update", "E2") for c in fd.calls))

    # 3. 同名検索は種類を絞る
    fd = _FakeDrive()
    quiet(find_by_name, fd, "matome", None, GDOC_MIME)
    check("find_by_name: mimeType で絞る", f"mimeType = '{GDOC_MIME}'" in fd.calls[0][1])

    # 4. フォルダ共有は upload より先に権限を付ける
    fd = _FakeDrive()
    args = build_parser().parse_args(["--file", str(doc), "--make-folder", "資料", "--share-with",
                                      "a@example.org", "--role", "editor", "--notify",
                                      "--credentials", "x", "--client", "y"])
    quiet(run, args, fd, "label", media)
    kinds = [c[0] for c in fd.calls]
    check("folder: 権限 → upload の順", kinds.index("perm") < max(i for i, k in enumerate(kinds) if k == "create"))
    perm = [c for c in fd.calls if c[0] == "perm"][0]
    check("role editor → writer、 通知あり", perm[3] == "writer" and perm[4] is True)

    # 5. 排他
    stopped = False
    try:
        quiet(run, build_parser().parse_args(["--file", str(doc), "--make-folder", "a", "--folder-id", "b",
                                              "--credentials", "x", "--client", "y"]), _FakeDrive(), "l", media)
    except SystemExit:
        stopped = True
    check("--make-folder と --folder-id は排他", stopped)

    # 6. shim 用: 認証の引数を差し替えられる
    p = build_parser(lambda ps: ps.add_argument("--account", default="a1", choices=["a1", "a2"]))
    a = p.parse_args(["--file", str(doc)])
    check("build_parser(add_account_args): 認証の引数を下層が足す", a.account == "a1" and not hasattr(a, "credentials"))
    print(f"drive-upload-share selftest: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    if sys.argv[1:] == ["--selftest"]:
        sys.exit(_selftest())
    main()
