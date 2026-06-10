#!/usr/bin/env bash
# docx-to-pdf.sh — convert a Word document (docx/doc) to PDF, cross-platform.
#
# Sibling of xlsx-to-pdf.sh (spreadsheets). python-docx / textutil can read or
# edit a .docx but cannot RENDER a PDF; producing a visual copy (to show, to
# attach, or to hand a form to someone to fill in) needs a real engine. This
# picks one automatically.
#
# Why a docx-specific script (not just "run soffice"):
#   On macOS, LibreOffice is often NOT installed (Microsoft Office + Pages are),
#   and office-automation.md marks LibreOffice as "not recommended on mac".
#   Reaching for `soffice` first is the exact failure mode this script prevents —
#   call this and it uses the right engine for the platform.
#
# Engine selection:
#   macOS (default) : Pages.app — most robust automation. WARNING: output is
#                     Pages' re-flow, NOT byte-faithful to Word (headings /
#                     side-by-side tables may shift). Fine for "show me / verify
#                     content / hand someone a form to fill".
#   --word          : Microsoft Word via osascript — layout-faithful, for a
#                     reviewer-facing copy. Handles the stale-cache + cold-start
#                     gotchas (full kill + shell `open` + warm-up sleep).
#   non-macOS       : LibreOffice (soffice / libreoffice) on PATH.
#
# Refs: conventions/office-automation.md  #docx-to-pdf-pages  #docx-pdf-stale-cache
#
# Usage:
#   docx-to-pdf.sh [--word] <input.docx> [output.pdf]
#     output.pdf  defaults to <input> with a .pdf extension, next to the source.
set -euo pipefail

ENGINE_WORD=0
if [ "${1:-}" = "--word" ]; then ENGINE_WORD=1; shift; fi

SRC="${1:?usage: docx-to-pdf.sh [--word] <input.docx> [output.pdf]}"
SRC="$(cd "$(dirname "$SRC")" && pwd)/$(basename "$SRC")"
[ -f "$SRC" ] || { echo "❌ not found: $SRC" >&2; exit 1; }
PDF="${2:-${SRC%.*}.pdf}"
case "$PDF" in /*) : ;; *) PDF="$(pwd)/$PDF" ;; esac
rm -f "$PDF"

have() { command -v "$1" >/dev/null 2>&1; }
soffice_bin() { if have soffice; then echo soffice; elif have libreoffice; then echo libreoffice; fi; }

render_pages() {
  # Robust macOS automation; uses the verified `export ... as PDF` form.
  osascript - "$SRC" "$PDF" <<'AS'
on run argv
  set srcPath to item 1 of argv
  set pdfPath to item 2 of argv
  with timeout of 200 seconds
    tell application "Pages"
      activate
      set theDoc to open POSIX file srcPath
      delay 2
      export theDoc to POSIX file pdfPath as PDF
      close theDoc saving no
    end tell
  end timeout
end run
AS
}

render_word() {
  # Word engine: stale in-memory cache + cold-start failures
  # (office-automation.md #docx-pdf-stale-cache). Defenses: full kill → shell
  # `open` (file association = cold-start safe) → warm-up sleep → save as the
  # active document. save-as syntax is Word-version dependent.
  pkill -x "Microsoft Word" 2>/dev/null || true
  sleep 2
  open "$SRC"
  sleep 5
  osascript -e "tell application \"Microsoft Word\" to save as active document file name \"$PDF\" file format format PDF"
  osascript -e 'tell application "Microsoft Word" to close active document saving no' >/dev/null 2>&1 || true
}

render_soffice() {
  local bin outdir profile gen
  bin="$(soffice_bin)"; [ -n "$bin" ] || return 1
  outdir="$(dirname "$PDF")"
  profile="$(mktemp -d)"; trap 'rm -rf "$profile"' RETURN
  "$bin" --headless -env:UserInstallation="file://$profile" \
      --convert-to pdf --outdir "$outdir" "$SRC" >/dev/null
  gen="$outdir/$(basename "${SRC%.*}").pdf"
  [ "$gen" = "$PDF" ] || mv -f "$gen" "$PDF"
}

if [ "$(uname)" = "Darwin" ]; then
  if [ "$ENGINE_WORD" = 1 ]; then
    render_word
  elif [ -d "/Applications/Pages.app" ]; then
    render_pages
  elif have soffice || have libreoffice; then
    render_soffice
  else
    render_word   # macOS without Pages: Word is the remaining option
  fi
else
  if have soffice || have libreoffice; then
    render_soffice
  else
    echo "❌ No conversion engine: install LibreOffice (soffice), or run on macOS (Pages/Word)." >&2
    exit 1
  fi
fi

[ -f "$PDF" ] || { echo "❌ conversion produced no PDF: $PDF" >&2; exit 1; }
echo "PDF: $PDF"
ls -la "$PDF"
