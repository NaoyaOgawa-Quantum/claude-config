#!/usr/bin/env python3
"""tex-rename-symbols.py — LaTeX 原稿の 1 文字記号 (y → x、 r → \\zeta_x の類) を安全に一括改名する (scan / apply)。

1 文字の記号は素の置換ができない: 同じ文字が \\command の中 (\\frac, \\right, \\sqrt)、 \\cite/\\ref の key、 別の記号の
添字 (\\sigma_z)、 英単語、 別の量 (Mandelstam の s と Bloch 成分の s、 Yukawa の y と Δm/Γ の y)、 `\\%` の後ろ、 に現れる。
本 script は「standalone な文字」 だけを対象にし、 曖昧な文字は呼び手が exact 置換の list で先に処理する。

standalone の定義 = 次をすべて満たす:
  * \\command 名の一部でない / \\cite \\ref \\label \\eqref \\cref \\begin \\end \\includegraphics \\bibliography 等の引数の中でない
  * `%` コメントの中でない (`\\%` は除外 = エスケープされた % はコメントでない)
  * 前後が英字でない (`ry^2` のような 2 文字連結は対象外 → exact list で)
  * 直前が `'` でない (英語の所有格 's)
  * 別の記号の添字・上付き全体でない (`_y`、 `_{y}` は対象外。 `_{r\\le0,y}` の r は対象)
  * --keep の正規表現 (文字の直後の文脈) に当たらない (例: Yukawa の `y}{2}S`)

使い方:
  tex-rename-symbols.py scan  FILE --letters ryz [--keep 'y(?=\\}\\{2\\}S)']
      standalone な出現を行番号と文脈つきで列挙する (置換前後の確認用)
  tex-rename-symbols.py apply FILE --map y=x --map 'r=\\zeta_x' --map 'z=\\zeta_z' [--exact exact.json] [--keep REGEX]... [--dry-run]
      exact.json = [["old literal","new literal"], ...] を先に当て (Bloch の s など standalone 規則で分けられない文字)、
      その後 --map の standalone 置換を 1 pass で当てる。 `\\bar X` は `\\bar{X}` に整える。 置換結果が後続の英字と
      連結する (例 `\\zeta_xx`) と assert で止まる。 --dry-run は件数だけ。

手順の正本 = conventions/latex.md#symbol-rename (走査 → exact → standalone → 再走査 → 図の label → 再組版 → PDF text 検査 → 同じ turn で commit)。
実測で踏んだ穴 = `%.*` でコメントを消すと `\\%` 以後の記号が黙って残る (本 script は (?<!\\\\)% を使う)。
"""
import argparse, json, re, sys

SKIP_ARGS = re.compile(r'\\(cite|ref|label|eqref|cref|labelcref|begin|end|includegraphics|bibliography|bibliographystyle|'
                       r'usepackage|documentclass|input|include)\*?(\[[^\]]*\])?\{[^}]*\}')


def build_mask(src):
    mask = bytearray(len(src))
    for rx in (SKIP_ARGS, re.compile(r'\\[A-Za-z]+'), re.compile(r'(?<!\\)%.*')):
        for m in rx.finditer(src):
            for i in range(m.start(), m.end()):
                mask[i] = 1
    return mask


def is_standalone(src, mask, i, keeps):
    if mask[i]:
        return False
    prev = src[i - 1] if i else ''
    nxt = src[i + 1] if i + 1 < len(src) else ''
    if prev.isalpha() or nxt.isalpha() or prev == "'":
        return False
    if prev in '_^':
        return False
    if prev == '{' and i >= 2 and src[i - 2] in '_^' and nxt == '}':
        return False
    for k in keeps:
        if k.match(src, i):
            return False
    return True


def scan(src, letters, keeps):
    mask = build_mask(src)
    out = {c: [] for c in letters}
    for m in re.finditer('[' + re.escape(letters) + ']', src):
        i = m.start()
        if is_standalone(src, mask, i, keeps):
            line = src.count('\n', 0, i) + 1
            out[m.group()].append((line, src[max(0, i - 28):i + 28].replace('\n', ' ')))
    return out


def apply(src, mapping, exact, keeps):
    for a, b in exact:
        n = src.count(a)
        if n:
            src = src.replace(a, b)
        print(f'exact x{n}: {a[:48]}', file=sys.stderr)
    mask = build_mask(src)
    out, last, counts = [], 0, {c: 0 for c in mapping}
    for m in re.finditer('[' + re.escape(''.join(mapping)) + ']', src):
        i, c = m.start(), m.group()
        if not is_standalone(src, mask, i, keeps):
            continue
        out.append(src[last:i]); out.append(mapping[c]); last = i + 1; counts[c] += 1
    out.append(src[last:]); new = ''.join(out)
    for c, rep in mapping.items():
        if rep.startswith('\\'):
            new = new.replace('\\bar ' + rep, '\\bar{' + rep.split('_')[0] + '}' + rep[len(rep.split('_')[0]):]) \
                     .replace('\\bar' + rep, '\\bar{' + rep.split('_')[0] + '}' + rep[len(rep.split('_')[0]):])
            bad = re.search(re.escape(rep) + r'[A-Za-z]', new)
            assert not bad, f'replacement {rep} merged with a following letter: …{new[max(0, bad.start()-30):bad.end()+10]}…'
    return new, counts


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    sub = ap.add_subparsers(dest='cmd', required=True)
    s = sub.add_parser('scan'); s.add_argument('file'); s.add_argument('--letters', required=True)
    s.add_argument('--keep', action='append', default=[])
    a = sub.add_parser('apply'); a.add_argument('file'); a.add_argument('--map', action='append', required=True)
    a.add_argument('--exact'); a.add_argument('--keep', action='append', default=[]); a.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()
    src = open(args.file, encoding='utf-8').read()
    keeps = [re.compile(k) for k in args.keep]
    if args.cmd == 'scan':
        for c, hits in scan(src, args.letters, keeps).items():
            print(f'===== {c}: {len(hits)}')
            for line, ctx in hits:
                print(f'{line:5d}  …{ctx}…')
        return
    mapping = dict(m.split('=', 1) for m in args.map)
    exact = json.load(open(args.exact, encoding='utf-8')) if args.exact else []
    new, counts = apply(src, mapping, exact, keeps)
    print('standalone replaced:', counts, file=sys.stderr)
    if args.dry_run:
        return
    open(args.file, 'w', encoding='utf-8').write(new)
    left = scan(new, ''.join(mapping), keeps)
    print('remaining standalone (should be 0 unless --keep):', {c: len(h) for c, h in left.items()}, file=sys.stderr)


if __name__ == '__main__':
    main()
