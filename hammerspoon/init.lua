-- CLI (hs コマンド) を有効化
require("hs.ipc")

-- Claude for Mac: Cmd+Q 誤終了防止 (長押しで終了)
-- Claude が前面のとき、 Cmd+Q を claudeQuitHoldSeconds 秒 (既定 1.5) 押し続けた
-- ときだけ Claude を終了する。 途中で Q か Cmd を離せば取り消し。
-- 秒数は ~/.hammerspoon/local.lua で claudeQuitHoldSeconds = 5 のように変えられる
-- (押した時に読むので、 local.lua が init.lua の後に読まれても効く)。
--
-- ⚠️ 終了の代わりのキーに Cmd+Shift+Q を案内しない: macOS では Cmd+Shift+Q は
-- 「ログアウト」 (Claude のメニューに無いので Apple メニューに落ちる)。
-- ⚠️ メニューバーの「Claude を終了」 は止められない (キー入力でないので tap に来ない)。
-- ⚠️ tap と timer は global に持つ。 local に入れると init.lua の実行が終わった後に
-- Lua の GC が回収し、 tap が黙って止まる (起動直後は効くので気づけない。
-- 実測 = 長く動かしている Hammerspoon で Cmd+Q が素通りして Claude が終了した)。
-- 名前は他の設定とぶつからないよう接頭辞つき。

claudeQuitHold = nil  -- 押している間だけ {timer, alert}

local function claudeQuitHoldCancel()
    if claudeQuitHold then
        claudeQuitHold.timer:stop()
        hs.alert.closeSpecific(claudeQuitHold.alert)
        claudeQuitHold = nil
    end
end

local types = hs.eventtap.event.types
claudeQuitTap = hs.eventtap.new({types.keyDown, types.keyUp, types.flagsChanged}, function(event)
    local t = event:getType()
    local flags = event:getFlags()
    local keyCode = event:getKeyCode()

    -- Cmd+Q (keyCode 12 = Q)、 他の修飾キーなし
    if t == types.keyDown and keyCode == 12
        and flags.cmd and not flags.shift and not flags.alt and not flags.ctrl then
        local app = hs.application.frontmostApplication()
        if app and app:name() == "Claude" then
            if not claudeQuitHold then  -- 押し始め (押しっぱなしのキーリピートは無視)
                local secs = claudeQuitHoldSeconds or 1.5
                local alert = hs.alert.show(
                    string.format("⌘Q を %g 秒押し続けると Claude を終了", secs), secs)
                claudeQuitHold = {
                    alert = alert,
                    timer = hs.timer.doAfter(secs, function()
                        claudeQuitHold = nil
                        app:kill()  -- 通常の終了 (強制終了ではない)
                    end),
                }
            end
            return true  -- Claude には渡さない
        end
    end

    -- 離したら取り消す (Q を離した / Cmd を離した)
    if claudeQuitHold and ((t == types.keyUp and keyCode == 12)
        or (t == types.flagsChanged and not flags.cmd)) then
        claudeQuitHoldCancel()
    end
    return false  -- 他はそのまま通す
end)
claudeQuitTap:start()

-- macOS は応答の遅い eventtap を無効にすることがある (sleep からの復帰後など)。
-- 止まっていたら 5 秒以内に再開する。
claudeQuitTapWatchdog = hs.timer.doEvery(5, function()
    if not claudeQuitTap:isEnabled() then
        claudeQuitTap:start()
    end
end)

-- クリップボード整形 + 貼り付け: ⌃⌥⌘V
-- PDF からコピーしたテキストの余分な改行・RTF 書式を除去し、 そのまま
-- 前面アプリに Cmd+V を送って貼り付ける (= 「ペーストしてスタイルを
-- 合わせる」 の整形版。 貼り付け先で押す)。
-- hotkey での明示発火のみ（常駐監視はしない、誤爆防止 +
-- conventions/secret-handoff.md のクリップボード単一資源原則と衝突させない）。
-- 整形ロジックの正本は scripts/clipboard-cleaner.py
-- （~/.hammerspoon/init.lua → repo への symlink を辿って解決する）。
local function cleanClipboardAndPaste()
    local initPath = os.getenv("HOME") .. "/.hammerspoon/init.lua"
    local target = hs.fs.symlinkAttributes(initPath, "target")
    local repoRoot = target and target:match("^(.*)/hammerspoon/init%.lua$")
    local cleaner = repoRoot and (repoRoot .. "/scripts/clipboard-cleaner.py")
    if not cleaner or not hs.fs.attributes(cleaner) then
        hs.alert.show("clipboard-cleaner.py が見つからない\n(init.lua が repo への symlink である必要あり)", 3)
        return
    end
    local output, ok = hs.execute("/usr/bin/python3 '" .. cleaner .. "' 2>&1")
    if ok then
        -- ⌃⌥⌘ が物理的に押されたままだと合成 Cmd+V にハードウェア修飾が
        -- 合流して paste にならない (実機で確認済の罠)。 全修飾キーの
        -- 解放を待ってから送る。
        hs.alert.show(output:gsub("%s+$", "") .. " → キーを離すと貼り付け", 1.5)
        hs.timer.waitUntil(
            function()
                local m = hs.eventtap.checkKeyboardModifiers()
                return not (m.cmd or m.alt or m.ctrl or m.shift or m.fn)
            end,
            function() hs.eventtap.keyStroke({"cmd"}, "v") end,
            0.05
        )
    else
        -- 失敗時 (= クリップボードが空 等) は貼り付けない
        hs.alert.show("clipboard-cleaner 失敗: " .. output, 3)
    end
end
hs.hotkey.bind({"ctrl", "alt", "cmd"}, "V", cleanClipboardAndPaste)

-- 個人層 / マシンローカル拡張の読み込み hook
-- ~/.hammerspoon/local.lua があれば末尾で読む（無ければ何もしない）。
-- 本ファイル (= layer 1 共有設定) を fork せずに個人の binding を
-- 足せるようにするための拡張点。個人層 repo のファイルへの symlink を
-- 置く運用を想定（hooks の layer-3 chain と同じ発想）。
local localLua = os.getenv("HOME") .. "/.hammerspoon/local.lua"
if hs.fs.attributes(localLua) then
    local ok, err = pcall(dofile, localLua)
    if not ok then
        hs.alert.show("local.lua の読み込みに失敗: " .. tostring(err), 4)
    end
end
