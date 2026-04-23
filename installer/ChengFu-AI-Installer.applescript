-- ============================================================
-- 承富 AI 系統 v1.1 · Mac 原生安裝精靈
-- ============================================================
-- 雙擊此 .app · GUI 對話框引導 IT 輸入 .env · 完成後自動
-- 啟動全 stack · 印出維運手冊
--
-- 編譯:installer/build.sh 用 osacompile 轉成 .app
-- 打包:installer/build.sh 把 .app 包成 ChengFu-AI-Installer.dmg
-- ============================================================

on run
	-- ============ 步驟 0 · 歡迎畫面 ============
	set welcomeText to "歡迎使用承富 AI 系統 v1.3.0 安裝精靈" & return & return & ¬
		"執行時間:30-45 分鐘(視網路)" & return & return & ¬
		"v1.2 4 功能:" & return & ¬
		"  🎤 會議速記 · 🎬 媒體 CRM · 📅 社群排程 · 📸 場勘 PWA" & return & ¬
		"v1.3.0 強化(20 PR · 2026-04-23):" & return & ¬
		"  · 13 V1.3-PLAN(12 ship · B1 真打 Meta 延 v1.4)" & return & ¬
		"  · 13 user-guide markdown(quickstart / mobile-ios / error-codes / training)" & return & ¬
		"  · 5 批 UX 升級(toast 標準化 / 8 view 空狀態 / Modal a11y / 27 shortcut)" & return & ¬
		"  · 行動端 bottom nav · WCAG 2.2 (skip-link / focus-visible / reduced-motion)" & return & ¬
		"  · 30+ hardening fixes(來自 5 agent deep audit)" & return & ¬
		"  · L3 server-side wall + OAuth URL encode + cookie verified audit" & return & ¬
		"  203 tests pass · 12/13 ship · B1 真 Meta + sync→async pymongo 留 v1.4" & return & return & ¬
		"請預先準備:" & return & ¬
		"  • Anthropic API Key(必須 · Tier 2 預存 USD $50)" & return & ¬
		"  • OpenAI API Key(會議速記 Whisper 用 · 必須)" & return & ¬
		"  • Fal.ai API Key(設計助手生圖 · 選配)" & return & ¬
		"  • Webhook URL(Slack/Discord/Telegram/Mattermost · 每位同事自設 · 安裝後在 launcher 設)" & return & ¬
		"  • 公司域名(計畫對外用)" & return & ¬
		"  • 管理員 email(預設 sterio068@gmail.com)" & return & ¬
		"  • Docker Desktop 已安裝且啟動" & return & return & ¬
		"按「繼續」開始 · 按「取消」結束"
	display dialog welcomeText with title "承富 AI 安裝 · 歡迎" buttons {"取消", "繼續"} default button "繼續" with icon note
	if button returned of result is "取消" then return

	-- ============ 步驟 1 · 環境檢查 ============
	-- osascript do shell script PATH 受限(只 /usr/bin:/bin 等)· homebrew docker 找不到
	-- 修:強制 PATH 含所有常見 docker 安裝位置 + Docker Desktop bundled bin
	set checkResult to do shell script "
export PATH=/opt/homebrew/bin:/usr/local/bin:/Applications/Docker.app/Contents/Resources/bin:$PATH
which docker > /dev/null 2>&1 && docker info > /dev/null 2>&1 && echo OK || echo MISSING
"
	if checkResult is not "OK" then
		-- 區分「沒裝」vs「裝了沒啟動」· 給更精確訊息
		set whichResult to do shell script "
export PATH=/opt/homebrew/bin:/usr/local/bin:/Applications/Docker.app/Contents/Resources/bin:$PATH
which docker > /dev/null 2>&1 && echo HAS || echo NONE
"
		if whichResult is "HAS" then
			display dialog "⚠ Docker 已安裝 · 但 daemon 未啟動" & return & return & ¬
				"請手動開 Docker Desktop(Applications → Docker)" & return & ¬
				"等鯨魚 icon 在 menu bar 變綠 · 然後重跑此安裝精靈" buttons {"關閉"} with icon caution
		else
			display dialog "❌ Docker Desktop 未安裝" & return & return & ¬
				"請先到 https://www.docker.com/products/docker-desktop/" & return & ¬
				"下載 + 安裝 + 啟動 Docker Desktop · 然後重跑此安裝精靈" buttons {"關閉"} with icon stop
		end if
		return
	end if

	-- 找 repo 路徑
	try
		set repoPath to do shell script "
# 安裝精靈在 .app 內 · 需找 repo
# 1. 嘗試 ~/ChengFu / ~/Workspace/ChengFu / ~/Desktop/ChengFu
# 2. 若都沒 · 提示 user clone
for d in \"$HOME/ChengFu\" \"$HOME/Workspace/ChengFu\" \"$HOME/Desktop/ChengFu\" \"$HOME/Documents/ChengFu\"; do
    if [[ -f \"$d/config-templates/docker-compose.yml\" ]]; then
        echo \"$d\"
        exit 0
    fi
done
echo NOT_FOUND
"
		if repoPath is "NOT_FOUND" then
			set userChoice to display dialog "找不到 ChengFu repo · 你想:" & return & return & ¬
				"A) 自動 clone 到 ~/ChengFu(需要 git + 網路)" & return & ¬
				"B) 手動指定路徑" buttons {"取消", "B 手動指定", "A 自動 clone"} default button "A 自動 clone"
			if button returned of userChoice is "取消" then return
			if button returned of userChoice is "A 自動 clone" then
				display dialog "正在 clone · 視網路速度約 1-3 分鐘 ..." giving up after 1
				do shell script "cd $HOME && git clone https://github.com/Sterio068/chengfu-ai.git ChengFu 2>&1"
				set repoPath to (do shell script "echo $HOME/ChengFu")
			else
				set repoChoice to choose folder with prompt "選 ChengFu repo 根目錄(含 config-templates/)"
				set repoPath to POSIX path of repoChoice
				set repoPath to do shell script "echo " & quoted form of repoPath & " | sed 's:/$::'"
			end if
		end if
	on error errMsg
		display dialog "找 repo 失敗:" & errMsg buttons {"關閉"} with icon stop
		return
	end try

	-- ============ 步驟 2 · 收集 .env 機密 ============
	-- 2a · Anthropic API Key
	set apiKeyDialog to display dialog ¬
		"請貼上 Anthropic API Key" & return & return & ¬
		"格式 sk-ant-xxx... · 從 https://console.anthropic.com 拿" & return & ¬
		"必須 Tier 2(預存 USD $50)" & return & return & ¬
		"⚠️ 此值會存進 macOS Keychain · 不會明文寫進 .env" ¬
		default answer "" with title "承富 AI 安裝 · 1/6" with hidden answer buttons {"取消", "下一步"} default button "下一步"
	if button returned of apiKeyDialog is "取消" then return
	set anthropicKey to text returned of apiKeyDialog
	if length of anthropicKey is less than 20 then
		display dialog "❌ API Key 太短 · 請確認是完整 sk-ant-xxx 格式" buttons {"關閉"} with icon stop
		return
	end if

	-- 2a-2 · OpenAI API Key(v1.2 · Whisper 會議速記用)
	set openaiKeyDialog to display dialog ¬
		"請貼上 OpenAI API Key(v1.2 必須 · 會議速記 Whisper STT 用)" & return & return & ¬
		"格式 sk-... · 從 https://platform.openai.com/api-keys 拿" & return & ¬
		"Tier 1 普通帳號就夠 · Whisper $0.006/分鐘" & return & return & ¬
		"留空可跳過 · 但會議速記功能不可用 · 之後可在「使用教學 → API Key」補設" ¬
		default answer "" with title "承富 AI 安裝 · 2/6" with hidden answer buttons {"取消", "下一步"} default button "下一步"
	if button returned of openaiKeyDialog is "取消" then return
	set openaiKey to text returned of openaiKeyDialog

	-- 2b · 公司域名(對外)· 暫時可空
	set domainDialog to display dialog ¬
		"請輸入承富對外域名(可暫時跳過 · 用本機 localhost)" & return & return & ¬
		"例:ai.chengfu.com.tw" & return & ¬
		"留空 → 本機開發模式 · 之後可手動改 .env" ¬
		default answer "" with title "承富 AI 安裝 · 3/6" buttons {"取消", "下一步"} default button "下一步"
	if button returned of domainDialog is "取消" then return
	set publicDomain to text returned of domainDialog

	-- 2c · 管理員 email
	set adminDialog to display dialog ¬
		"請輸入承富 AI 管理員 email" & return & return & ¬
		"白名單內 user 才能用 admin endpoint" ¬
		default answer "sterio068@gmail.com" with title "承富 AI 安裝 · 4/6" buttons {"取消", "下一步"} default button "下一步"
	if button returned of adminDialog is "取消" then return
	set adminEmail to text returned of adminDialog

	-- 2d · 知識庫 NAS 路徑(選填)
	set nasDialog to display dialog ¬
		"請輸入 NAS 掛載路徑(可暫時跳過)" & return & return & ¬
		"例:/Volumes/chengfu-nas/projects" & return & ¬
		"留空 → 用 /tmp/chengfu-test-sources(本機測試)" ¬
		default answer "" with title "承富 AI 安裝 · 5/6" buttons {"取消", "下一步"} default button "下一步"
	if button returned of nasDialog is "取消" then return
	set nasPath to text returned of nasDialog

	-- 2e · 確認啟動
	set domainDisplay to publicDomain
	if publicDomain is "" then set domainDisplay to "(本機 only · localhost)"
	set nasDisplay to nasPath
	if nasPath is "" then set nasDisplay to "(本機 /tmp 測試)"

	set confirmText to "已收集設定 · 確認啟動?" & return & return & ¬
		"• Repo 路徑:" & repoPath & return & ¬
		"• Anthropic Key:已收(隱藏)" & return & ¬
		"• 對外域名:" & domainDisplay & return & ¬
		"• 管理員 email:" & adminEmail & return & ¬
		"• NAS 路徑:" & nasDisplay & return & return & ¬
		"按「啟動安裝」會:" & return & ¬
		"  1. 寫入 macOS Keychain" & return & ¬
		"  2. 建 .env · 注入 prod fail-closed env" & return & ¬
		"  3. 抓 5 個 Docker image(LibreChat / Mongo / Meili / nginx / accounting)" & return & ¬
		"  4. 啟動 6 容器 · 等 healthy" & return & ¬
		"  5. 跑 smoke test · 印維運手冊"
	display dialog confirmText with title "承富 AI 安裝 · 6/6 確認" buttons {"上一步取消", "啟動安裝"} default button "啟動安裝"

	-- ============ 步驟 3 · 寫 Keychain + .env ============
	-- 用 do shell script · 隱藏終端機
	try
		do shell script ¬
			"security delete-generic-password -s 'chengfu-ai-anthropic-key' 2>/dev/null; " & ¬
			"security add-generic-password -a $USER -s 'chengfu-ai-anthropic-key' -w " & quoted form of anthropicKey & " 2>&1"
		-- v1.2 · OpenAI key 也寫 Keychain(若 user 有填)
		if openaiKey is not "" and length of openaiKey > 10 then
			do shell script ¬
				"security delete-generic-password -s 'chengfu-ai-openai-key' 2>/dev/null; " & ¬
				"security add-generic-password -a $USER -s 'chengfu-ai-openai-key' -w " & quoted form of openaiKey & " 2>&1"
		end if

		-- 自動產 JWT / CREDS / Meili / Internal token
		do shell script "
SERVICE='chengfu-ai'
gen_secret() {
    local key=\"$1\"
    if ! security find-generic-password -s \"${SERVICE}-${key}\" -w > /dev/null 2>&1; then
        local val=$(openssl rand -hex 32)
        security add-generic-password -a $USER -s \"${SERVICE}-${key}\" -w \"$val\"
    fi
}
gen_secret jwt-secret
gen_secret jwt-refresh-secret
gen_secret creds-key
gen_secret meili-master-key
gen_secret internal-token
# CREDS-IV 是 16 byte
if ! security find-generic-password -s 'chengfu-ai-creds-iv' -w > /dev/null 2>&1; then
    iv=$(openssl rand -hex 16)
    security add-generic-password -a $USER -s 'chengfu-ai-creds-iv' -w \"$iv\"
fi
echo OK
"
	on error errMsg
		display dialog "❌ Keychain 寫入失敗:" & errMsg buttons {"關閉"} with icon stop
		return
	end try

	-- 寫 .env(AppleScript 不支援 inline if · 用 if-block 算字串)
	set isProd to (publicDomain is not "")
	set envMode to "development"
	set envLegacy to "1"
	set envDomain to "http://localhost"
	if isProd then
		set envMode to "production"
		set envLegacy to "0"
		set envDomain to "https://" & publicDomain
	end if

	set envKnowledge to "/Volumes,/data,/tmp/chengfu-test-sources"
	if nasPath is not "" then set envKnowledge to nasPath & ",/Volumes,/data"

	set envContent to "# 承富 AI v1.1 · 自動產自 ChengFu-AI-Installer.app · 2026-04-22" & return & ¬
		"NODE_ENV=" & envMode & return & ¬
		"ECC_ENV=" & envMode & return & ¬
		"ALLOW_LEGACY_AUTH_HEADERS=" & envLegacy & return & ¬
		"DOMAIN_CLIENT=" & envDomain & return & ¬
		"DOMAIN_SERVER=" & envDomain & return & ¬
		"ADMIN_EMAIL=" & adminEmail & return & ¬
		"ADMIN_EMAILS=" & adminEmail & return & ¬
		"ALLOW_REGISTRATION=false" & return & ¬
		"MONGO_URI=mongodb://mongodb:27017/chengfu" & return & ¬
		"SEARCH=true" & return & ¬
		"MEILI_HOST=http://meilisearch:7700" & return & ¬
		"KNOWLEDGE_ALLOWED_ROOTS=" & envKnowledge & return

	do shell script "echo " & quoted form of envContent & " > " & quoted form of (repoPath & "/config-templates/.env")

	-- ============ 步驟 4 · 開 Terminal 跑 docker compose(讓 IT 看到進度)============
	-- 用 Terminal 開新 window 跑 start.sh · IT 看見 docker 進度
	set scriptPath to repoPath & "/scripts/start.sh"
	set logFile to repoPath & "/installer-progress.log"

	-- 在 Terminal 顯示進度
	tell application "Terminal"
		activate
		do script "cd " & quoted form of repoPath & " && echo '═══ 承富 AI 安裝 · 抓 image + 啟動容器 ═══' && cd config-templates && docker compose pull && cd .. && bash scripts/start.sh && bash scripts/smoke-test.sh && echo '' && echo '✅ 安裝完成 · 訪問 http://localhost/' && echo '可關閉此 Terminal'"
	end tell

	-- 等 60 秒讓 docker 拉 + 啟動
	delay 60

	-- 檢查 healthz
	set healthOK to do shell script "curl -sf http://localhost/healthz > /dev/null 2>&1 && echo OK || echo WAIT"
	set retries to 0
	repeat while healthOK is "WAIT" and retries < 30
		delay 5
		set healthOK to do shell script "curl -sf http://localhost/healthz > /dev/null 2>&1 && echo OK || echo WAIT"
		set retries to retries + 1
	end repeat

	-- ============ 步驟 5 · 印維運手冊 ============
	if healthOK is "OK" then
		display dialog "🎯 承富 AI 系統 v1.2 安裝完成!" & return & return & ¬
			"訪問入口:" & return & ¬
			"  • Launcher 首頁:http://localhost/" & return & ¬
			"  • LibreChat 對話:http://localhost/chat" & return & ¬
			"  • 健康檢查:http://localhost/healthz" & return & ¬
			"  • Uptime 監控:http://localhost:3001" & return & return & ¬
			"v1.2 4 個新功能(左側 sidebar):" & return & ¬
			"  🎤 會議速記 · 🎬 媒體 CRM · 📅 社群排程 · 📸 場勘" & return & return & ¬
			"下一步(在 Terminal 跑):" & return & ¬
			"  cd " & repoPath & return & ¬
			"  python3 scripts/create-users.py" & return & ¬
			"  python3 scripts/create-agents.py" & return & ¬
			"  python3 scripts/upload-knowledge-base.py" & return & ¬
			"  ./scripts/install-launchd.sh  # 5 個 cron(含 social-scheduler)" & return & return & ¬
			"提醒同事:" & return & ¬
			"  • 進「使用教學」綁 Webhook(Slack/Discord/Telegram/Mattermost · 標案截止 / 預算警告會推)" & return & ¬
			"  • iPhone 場勘:設定 → 相機 → 格式 → 最相容(JPEG)" & return & return & ¬
			"完整文件:" & repoPath & "/docs/RELEASE-NOTES-v1.2.md" & return & ¬
			"問題找:sterio068@gmail.com" ¬
			with title "✅ 安裝完成" buttons {"開啟 Launcher", "稍後"} default button "開啟 Launcher"
		if button returned of result is "開啟 Launcher" then
			do shell script "open http://localhost/"
		end if
	else
		display dialog "⚠️ 容器啟動 · 但 healthz 還沒回 200" & return & return & ¬
			"看 Terminal 視窗 · 確認 docker compose 進度" & return & ¬
			"或跑:" & return & ¬
			"  cd " & repoPath & return & ¬
			"  ./scripts/smoke-test.sh" & return & return & ¬
			"問題找:sterio068@gmail.com" with title "⚠️ 部分完成" buttons {"關閉"} with icon caution
	end if
end run
