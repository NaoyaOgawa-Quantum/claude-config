-- CLI (hs コマンド) を有効化
require("hs.ipc")

-- Claude for Mac: Cmd+Q 誤終了防止
-- eventtap で低レベルにキーイベントを捕捉し、
-- Claude 宛の Cmd+Q をブロックする

local quitTap = hs.eventtap.new({hs.eventtap.event.types.keyDown}, function(event)
    local flags = event:getFlags()
    local keyCode = event:getKeyCode()

    -- Cmd+Q (keyCode 12 = Q) かつ Shift なし
    if flags.cmd and not flags.shift and not flags.alt and not flags.ctrl and keyCode == 12 then
        -- フロントアプリが Claude かチェック
        local app = hs.application.frontmostApplication()
        if app and app:name() == "Claude" then
            hs.alert.show("Quit Claude: Cmd+Shift+Q", 1)
            return true  -- イベントを消費（quit を阻止）
        end
    end
    return false  -- 他はそのまま通す
end)
quitTap:start()

-- クリップボード整形: ⌃⌥⌘V
-- PDF からコピーしたテキストの余分な改行・RTF 書式を除去する。
-- hotkey での明示発火のみ（常駐監視はしない、誤爆防止 +
-- conventions/secret-handoff.md のクリップボード単一資源原則と衝突させない）。
-- 整形ロジックの正本は scripts/clipboard-cleaner.py
-- （~/.hammerspoon/init.lua → repo への symlink を辿って解決する）。
local function cleanClipboard()
    local initPath = os.getenv("HOME") .. "/.hammerspoon/init.lua"
    local target = hs.fs.symlinkAttributes(initPath, "target")
    local repoRoot = target and target:match("^(.*)/hammerspoon/init%.lua$")
    local cleaner = repoRoot and (repoRoot .. "/scripts/clipboard-cleaner.py")
    if not cleaner or not hs.fs.attributes(cleaner) then
        hs.alert.show("clipboard-cleaner.py が見つからない\n(init.lua が repo への symlink である必要あり)", 3)
        return
    end
    local output, ok = hs.execute("/usr/bin/python3 '" .. cleaner .. "' 2>&1")
    hs.alert.show(ok and output:gsub("%s+$", "") or "clipboard-cleaner 失敗: " .. output, 2)
end
hs.hotkey.bind({"ctrl", "alt", "cmd"}, "V", cleanClipboard)
