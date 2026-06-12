#!/usr/bin/env python3
"""クリップボード一発整形 CLI — PDF からコピーしたテキストの後始末。

PDF からコピーしたテキストをそのまま貼ると、(a) 段落内の見た目改行が
そのまま入る、(b) RTF 書式（イタリック等）が付いてくる、の 2 つが起きる。
本スクリプトは「明示的に呼ばれた時だけ」クリップボードを 1 回整形する:

  - 段落内の改行を除去（空行 = 段落区切りは保持）
  - 行境界が日本語ならそのまま、英語ならスペースを挟んで結合
  - 英語のハイフネーション（行末 "beauti-" + "ful"）を復元
  - pbcopy で書き戻すことで RTF 書式も除去される（改行が無くても効く）

常駐監視はしない（conventions/clipboard-cleaner.md、secret-handoff.md の
クリップボード単一資源原則と衝突させないため）。

使い方:
  clipboard-cleaner.py            # クリップボードを整形して上書き
  clipboard-cleaner.py --stdin    # stdin → stdout のフィルタ（テスト用）
  clipboard-cleaner.py --selftest # 内蔵テスト

整形ロジックは scripts/pdf-cleaner.html (ブラウザ版 fallback) と仕様を
揃えてある。変更時は両方を更新すること。
"""

import os
import re
import subprocess
import sys

# 日本語判定: 全角スペース・記号・かな (U+3000-30FF)、CJK 統合漢字
# (U+4E00-9FFF)、全角英数 (U+FF00-FFEF)。pdf-cleaner.html と同一範囲。
JA_RE = re.compile(r'[　-ヿ一-鿿＀-￯]')


def _pb_env():
    """pbcopy/pbpaste 用の環境変数。

    C ロケール（LANG 未設定）だと pbcopy は「日本語 + 改行」入力で
    **silent に空クリップボードを作る**（日本語のみ・ASCII のみなら通る）。
    Hammerspoon の hs.execute や launchd 配下は LANG 未設定なので、
    呼び出し元の環境に頼らず常に UTF-8 を明示する。
    """
    env = dict(os.environ)
    env.pop('LC_ALL', None)  # LC_ALL は LC_CTYPE より優先されるため除去
    env['LC_CTYPE'] = 'UTF-8'
    return env


def clean(text):
    """段落内の改行を除去してテキストをつなぐ。

    返り値: (整形後テキスト, 結合した行境界の数)
    """
    joins = 0
    paragraphs = re.split(r'\n{2,}', text)

    cleaned = []
    for para in paragraphs:
        lines = [l.rstrip() for l in para.split('\n') if l.strip()]
        joined = ''
        for line in lines:
            if not joined:
                joined = line
                continue
            joins += 1
            if re.search(r'[A-Za-z]-$', joined):
                # 英語のハイフネーション: ハイフンを除いて直結
                joined = joined[:-1] + line
            elif JA_RE.search(joined[-1:]) or JA_RE.search(line[:1]):
                # 行境界のどちらかが日本語: スペース無しで直結
                joined += line
            else:
                # 英語同士: スペースを挟む
                joined += ' ' + line
        if joined:
            cleaned.append(joined)

    return '\n\n'.join(cleaned), joins


def clean_clipboard():
    env = _pb_env()
    text = subprocess.run(['pbpaste'], capture_output=True,
                          encoding='utf-8', env=env).stdout
    if not text.strip():
        print('クリップボードにテキストがありません')
        return 1
    result, joins = clean(text)
    # 改行除去が無くても書き戻す = pbcopy 経由で RTF 書式が落ちる
    subprocess.run(['pbcopy'], input=result, encoding='utf-8',
                   env=env, check=True)
    if joins:
        print(f'整形しました（改行 {joins} 箇所を結合・書式除去）')
    else:
        print('書式のみ除去（改行の変更なし）')
    return 0


def selftest():
    cases = [
        # (入力, 期待出力, 説明)
        ('日本語の文が\n途中で切れている',
         '日本語の文が途中で切れている', '日本語: スペース無し結合'),
        ('This line is\nwrapped here',
         'This line is wrapped here', '英語: スペース結合'),
        ('a beau-\ntiful day',
         'a beautiful day', 'ハイフネーション復元'),
        ('段落一の文章が\nここまで\n\n段落二の文章が\nここまで',
         '段落一の文章がここまで\n\n段落二の文章がここまで', '空行 = 段落区切りは保持'),
        ('日本語のあとに English\nfollows here',
         '日本語のあとに English follows here', '混在: 境界が英語ならスペース'),
        ('English then\n日本語が続く',
         'English then日本語が続く', '混在: 境界が日本語なら直結'),
        ('変更なしの一行', '変更なしの一行', '単一行は不変'),
    ]
    failed = 0
    for src, expect, desc in cases:
        got, _ = clean(src)
        if got != expect:
            print(f'FAIL: {desc}\n  expect: {expect!r}\n  got:    {got!r}')
            failed += 1
    total = len(cases)
    print(f'{total - failed}/{total} passed')
    return 1 if failed else 0


def main():
    if '--selftest' in sys.argv:
        return selftest()
    if '--stdin' in sys.argv:
        result, _ = clean(sys.stdin.read())
        sys.stdout.write(result)
        return 0
    return clean_clipboard()


if __name__ == '__main__':
    sys.exit(main())
