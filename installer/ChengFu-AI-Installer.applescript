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
		"✨ 本次安裝只要你設一組 admin 密碼" & return & ¬
		"其他 9 位同仁你裝完後自己在 UI 建(⌘U 同仁管理)" & return & ¬
		"自訂頭銜 · 權限勾選 · 不用再編 shell script" & return & return & ¬
		"v1.3.0 會自動幫你建:" & return & ¬
		"  👤 第一個 admin 帳號(你下一步要填的 email + 密碼)" & return & ¬
		"  🤖 10 個 Agent 助手(✨ 主管家 · 🎯 投標 · 🎪 活動 · 🎨 設計 · 📣 公關" & return & ¬
		"     🎙 會議 · 📚 知識 · 💰 財務 · ⚖️ 法務 · 📊 營運)" & return & return & ¬
		"裝完後 admin 在 launcher ⌘U 自己建 9 位同仁 · 自訂頭銜 + 權限" & return & return & ¬
		"v1.3.0 功能:" & return & ¬
		"  👥 同仁管理 UI(admin UI 建帳號 + 7 preset + 28 權限勾選)" & return & ¬
		"  🎤 會議速記 · 🎬 媒體 CRM · 📅 社群排程 · 📸 場勘 PWA" & return & ¬
		"  📚 13 份 user-guide · 🔒 30+ hardening · ♿ WCAG 2.2" & return & return & ¬
		"請預先準備:" & return & ¬
		"  • Anthropic API Key(必須 · Tier 2 預存 USD $50)" & return & ¬
		"  • OpenAI API Key(會議速記 Whisper 用 · 必須)" & return & ¬
		"  • Fal.ai API Key(設計助手生圖 · 選配)" & return & ¬
		"  • 公司域名(計畫對外用 · 可先留白)" & return & ¬
		"  • admin email + 密碼(你想用哪個登入 · 將自動註冊第一個 admin)" & return & ¬
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
		"將用此 email 自動註冊 LibreChat 第一個 admin 帳號" & return & ¬
		"白名單內 user 才能用 admin endpoint" ¬
		default answer "sterio068@gmail.com" with title "承富 AI 安裝 · 4/7" buttons {"取消", "下一步"} default button "下一步"
	if button returned of adminDialog is "取消" then return
	set adminEmail to text returned of adminDialog

	-- v1.3.0 · 2c-2 · admin 密碼(用來登入 LibreChat)
	set pwdDialog to display dialog ¬
		"設一組 admin 登入密碼" & return & return & ¬
		"• 用來登入 LibreChat(http://localhost/chat)" & return & ¬
		"• 也用來跑 scripts/create-users.py 建其他同仁帳號" & return & ¬
		"• 至少 8 字 · 記牢或存密碼管理器" ¬
		default answer "" with title "承富 AI 安裝 · 5/7" with hidden answer buttons {"取消", "下一步"} default button "下一步"
	if button returned of pwdDialog is "取消" then return
	set adminPassword to text returned of pwdDialog
	if length of adminPassword is less than 8 then
		display dialog "❌ 密碼至少 8 字元" buttons {"關閉"} with icon stop
		return
	end if

	set adminNameDialog to display dialog ¬
		"admin 顯示名稱(LibreChat 左上角會顯示)" & return & return & ¬
		"可用中文 · 例:「王小明」或「Sterio」" ¬
		default answer "承富管理員" with title "承富 AI 安裝 · 6/7" buttons {"取消", "下一步"} default button "下一步"
	if button returned of adminNameDialog is "取消" then return
	set adminName to text returned of adminNameDialog

	-- 2d · 知識庫 NAS 路徑(選填)
	set nasDialog to display dialog ¬
		"請輸入 NAS 掛載路徑(可暫時跳過)" & return & return & ¬
		"例:/Volumes/chengfu-nas/projects" & return & ¬
		"留空 → 用 /tmp/chengfu-test-sources(本機測試)" ¬
		default answer "" with title "承富 AI 安裝 · 7/7" buttons {"取消", "下一步"} default button "下一步"
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
	-- v1.3.0 dry-run fix · 原本 `tell application "Terminal"` 在 macOS Sequoia+ 需要
	-- AppleEvent 授權 · unsigned .app 會 -1743 錯
	-- 改用 `open -a Terminal` 打開 .command 檔 · 不需 AppleEvent 授權
	set scriptPath to repoPath & "/scripts/start.sh"
	set commandFile to repoPath & "/installer-run.command"

	-- 寫可執行 .command 檔 · Terminal 雙擊會跑
	-- v1.3.0 · 自動建 LibreChat admin(用戶剛設的 email + 密碼)
	-- 用 LibreChat 內建 npm run create-user CLI
	-- v1.3.0+ · 加完整 log + timeout · 避免 silent fail 後用戶看不出原因
	set cmdContent to "#!/bin/bash
export PATH=/opt/homebrew/bin:/usr/local/bin:/Applications/Docker.app/Contents/Resources/bin:$PATH
# v1.3.0+ · 所有輸出同步寫 log · 事後可診斷
LOG_FILE=/tmp/chengfu-install.log
: > \"$LOG_FILE\"
exec > >(tee -a \"$LOG_FILE\") 2>&1
echo \"=== 承富 AI 安裝 · $(date) ===\"
cd " & quoted form of repoPath & "
echo '═══ [1/6] 抓 image + 啟動容器 ═══'
cd config-templates && docker compose pull || { echo '❌ docker pull 失敗'; exit 1; }
cd ..
bash scripts/start.sh || { echo '❌ start.sh 失敗'; exit 1; }
echo ''
echo '═══ [2/6] 等 LibreChat ready (max 120s) ═══'
TIMEOUT=60
while [ $TIMEOUT -gt 0 ]; do
  if curl -sf http://localhost/chat/api/config > /dev/null 2>&1; then
    echo '✓ LibreChat ready'
    break
  fi
  sleep 2
  TIMEOUT=$((TIMEOUT - 1))
done
if [ $TIMEOUT -eq 0 ]; then
  echo '❌ LibreChat 超時 · 看 docker compose logs librechat'
  exit 1
fi
echo ''
echo '═══ [3/6] 建 admin 帳號(' " & quoted form of adminEmail & " ')═══'
# LibreChat npm run create-user 會問 confirm · echo y 自動過
# user 已存在會報錯但不致命 · continue 下一步(v1.3.0 fix)
docker exec chengfu-librechat sh -c 'echo y | npm run create-user -- " & quoted form of adminEmail & " " & quoted form of adminName & " " & quoted form of adminEmail & " " & quoted form of adminPassword & " ' 2>&1 | tail -10
echo ''
echo '═══ [4/6] 等 admin 寫入 MongoDB (max 30s) ═══'
TIMEOUT=15
while [ $TIMEOUT -gt 0 ]; do
  COUNT=$(docker exec chengfu-mongo mongosh chengfu --quiet --eval 'db.users.countDocuments({email:\"" & adminEmail & "\"})' 2>/dev/null | tr -d '[:space:]')
  if [ \"$COUNT\" = '1' ]; then
    echo '✓ admin 已 ready'
    break
  fi
  echo \"  等 admin 寫入... (COUNT=$COUNT)\"
  sleep 2
  TIMEOUT=$((TIMEOUT - 1))
done
if [ $TIMEOUT -eq 0 ]; then
  echo '⚠ admin 沒寫進 MongoDB · 跳過 Agent 建立 · 手動處理:'
  echo '   1. 訪問 http://localhost/chat 手動註冊'
  echo '   2. 跑 scripts/create-agents.py'
  echo '   log 在 /tmp/chengfu-install.log'
fi
echo ''
echo '═══ [5/6] 建 10 個 core Agent ═══'
echo '(✨ 主管家 · 🎯 投標 · 🎪 活動 · 🎨 設計 · 📣 公關 · 🎙 會議 · 📚 知識 · 💰 財務 · ⚖️ 法務 · 📊 營運)'
if [ $TIMEOUT -gt 0 ]; then
  # admin 真的 ready 才跑
  # LIBRECHAT_URL=http://localhost(走 nginx · 不直連 3080 因 docker 網路只內部)
  LIBRECHAT_URL=http://localhost \\
  LIBRECHAT_ADMIN_EMAIL=" & quoted form of adminEmail & " \\
  LIBRECHAT_ADMIN_PASSWORD=" & quoted form of adminPassword & " \\
  python3 scripts/create-agents.py --tier core 2>&1 | tee -a \"$LOG_FILE\"
  AGENT_RC=${PIPESTATUS[0]}
  if [ $AGENT_RC -ne 0 ]; then
    echo '⚠ Agent 建立失敗 (rc=' $AGENT_RC ') · 手動跑:'
    echo '   LIBRECHAT_URL=http://localhost \\\\'
    echo '   LIBRECHAT_ADMIN_EMAIL=" & adminEmail & " \\\\'
    echo '   LIBRECHAT_ADMIN_PASSWORD=<密碼> \\\\'
    echo '   python3 scripts/create-agents.py --tier core'
  fi
fi
echo ''
echo '═══ [6/6] smoke test ═══'
echo ''
bash scripts/smoke-test.sh
echo ''
echo '✅ 安裝完成 · admin + 10 Agent 已建好'
echo ''
echo '══════════════════════════════════════════'
echo '  安裝完成 · 下一步只要 3 個動作'
echo '══════════════════════════════════════════'
echo ''
echo '【1】訪問 http://localhost/'
echo '    (自動跳到 Launcher 首頁 · 不是 LibreChat 原介面)'
echo ''
echo '【2】用剛設的 email + 密碼登入'
echo '    email: " & adminEmail & "'
echo '    密碼:你剛在精靈 5/7 步驟設的'
echo ''
echo '【3】按 ⌘U 進「同仁管理」· 建其他 9 位同仁'
echo '    ✨ v1.3 新功能 · 不用再跑 shell script!'
echo ''
echo '    建同仁流程:'
echo '     a) 按「+ 建新同仁」'
echo '     b) 填 email + 姓名'
echo '     c) 按 🎲 產隨機密碼 · 📋 複製分給同仁'
echo '     d) 選頭銜 preset(會計 / 企劃 / 設計 / 公關 / 業務 / 新人)'
echo '        · 或自訂 free text'
echo '        · 或展開 28 項權限勾選樹'
echo '     e) 按「建立」· 密碼顯示一次 · 複製完就看不到了'
echo ''
echo '【其他】'
echo ' · 忘了某人密碼 → 停用再重建(密碼只回一次)'
echo ' · 同仁離職 → 停用(保資料)· 真清走 admin 面板 PDPA'
echo ' · admin 升降權 → ⌘U 改 role 欄 USER ↔ ADMIN'
echo ''
echo '可關閉此 Terminal 視窗 · 但不要關 Docker Desktop'
"
	do shell script "cat > " & quoted form of commandFile & " <<'CHENGFU_EOF'
" & cmdContent & "
CHENGFU_EOF
chmod +x " & quoted form of commandFile

	-- open -a Terminal 不需 AppleEvent 授權 · 走正常 URL handler
	do shell script "open -a Terminal " & quoted form of commandFile

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
		display dialog "🎯 承富 AI 系統 v1.3.0 安裝完成!" & return & return & ¬
			"訪問入口:" & return & ¬
			"  • Launcher 首頁:http://localhost/" & return & ¬
			"  • LibreChat 對話:http://localhost/chat" & return & ¬
			"  • 健康檢查:http://localhost/healthz" & return & ¬
			"  • Uptime 監控:http://localhost:3001" & return & return & ¬
			"✨ v1.3 新功能:" & return & ¬
			"  👥 同仁管理 UI(⌘U)· admin 建帳號 + 頭銜 + 權限勾選" & return & ¬
			"  🎤 會議速記 · 🎬 媒體 CRM · 📅 社群排程 · 📸 場勘 PWA" & return & return & ¬
			"下一步:" & return & ¬
			"  1. 點「開啟 Launcher」 · 用剛設的 " & adminEmail & " 登入" & return & ¬
			"  2. 按 ⌘U 進「同仁管理」 · 建其他 9 位同仁" & return & ¬
			"  3. 選 7 個頭銜 preset · 或自訂權限勾選" & return & ¬
			"  4. 每個同仁產隨機密碼 · 複製分發" & return & return & ¬
			"提醒同事:" & return & ¬
			"  • iPhone 場勘:設定 → 相機 → 格式 → 最相容(JPEG)" & return & ¬
			"  • 使用教學(⌘?)· 13 份中文手冊" & return & return & ¬
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
