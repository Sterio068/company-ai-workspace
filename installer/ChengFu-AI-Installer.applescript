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
		"🔁 若已安裝過,會先偵測既有 .env + Keychain,可一鍵沿用不用重填" & return & ¬
		"✨ 本次安裝只要你設一組 admin 密碼" & return & ¬
		"其他 9 位同仁你裝完後自己在 UI 建(⌘U 同仁管理)" & return & ¬
		"自訂頭銜 · 權限勾選 · 不用再編 shell script" & return & return & ¬
		"v1.3.0 會自動幫你建:" & return & ¬
		"  👤 第一個 admin 帳號(你下一步要填的 email + 密碼)" & return & ¬
		"  🤖 10 個 Agent 助手(OpenAI 預設 · Claude 可切換備援)" & return & ¬
		"     ✨ 主管家 · 🎯 投標 · 🎪 活動 · 🎨 設計 · 📣 公關" & return & ¬
		"     🎙 會議 · 📚 知識 · 💰 財務 · ⚖️ 法務 · 📊 營運)" & return & return & ¬
		"裝完後 admin 在 launcher ⌘U 自己建 9 位同仁 · 自訂頭銜 + 權限" & return & return & ¬
		"v1.3.0 功能:" & return & ¬
		"  👥 同仁管理 UI(admin UI 建帳號 + 7 preset + 28 權限勾選)" & return & ¬
		"  🎤 會議速記 · 🎬 媒體 CRM · 📅 社群排程 · 📸 場勘 PWA" & return & ¬
		"  📚 13 份 user-guide · 🔒 30+ hardening · ♿ WCAG 2.2" & return & return & ¬
		"請預先準備:" & return & ¬
		"  • OpenAI API Key(必須 · 主力 AI 引擎)" & return & ¬
		"    取得網址:https://platform.openai.com/api-keys" & return & ¬
		"  • Anthropic API Key(選配 · Claude 備援)" & return & ¬
		"    取得網址:https://console.anthropic.com/settings/keys" & return & ¬
		"  • Fal.ai API Key(設計助手生圖 · 選配 · 裝完可在中控設定)" & return & ¬
		"    取得網址:https://fal.ai/dashboard/keys" & return & ¬
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
# 1. 嘗試 ~/Workspace/ChengFu / ~/ChengFu / ~/Desktop/ChengFu
# 2. 若都沒 · 提示 user clone
for d in \"$HOME/Workspace/ChengFu\" \"$HOME/ChengFu\" \"$HOME/Desktop/ChengFu\" \"$HOME/Documents/ChengFu\"; do
    if [[ -f \"$d/config-templates/docker-compose.yml\" ]]; then
        echo \"$d\"
        exit 0
    fi
done
		echo NOT_FOUND
"
		if repoPath is "NOT_FOUND" then
			-- vNext installer · 若 .dmg 內有 ChengFu-source.tar.gz,優先展開內建快照。
			-- 這避免本機最新改動尚未 push 時,安裝精靈 clone 到 GitHub 舊版。
			set appBundlePath to POSIX path of (path to me)
			set bundledRepo to do shell script "
APP_BUNDLE=" & quoted form of appBundlePath & "
APP_PARENT=$(dirname \"$APP_BUNDLE\")
SOURCE_TGZ=\"$APP_PARENT/ChengFu-source.tar.gz\"
TARGET=\"$HOME/ChengFu\"
if [[ -f \"$SOURCE_TGZ\" ]]; then
    rm -rf \"$TARGET.tmp\"
    mkdir -p \"$TARGET.tmp\"
    tar -xzf \"$SOURCE_TGZ\" -C \"$TARGET.tmp\"
    if [[ -e \"$TARGET\" ]]; then
        TS=$(date +%Y%m%d-%H%M%S)
        mv \"$TARGET\" \"$TARGET.backup-$TS\"
    fi
    mv \"$TARGET.tmp\" \"$TARGET\"
    echo \"$TARGET\"
else
    echo NOT_FOUND
fi
"
			if bundledRepo is not "NOT_FOUND" then
				set repoPath to bundledRepo
			else
				set userChoice to display dialog "找不到 ChengFu repo · 你想:" & return & return & ¬
					"A) 自動 clone 到 ~/ChengFu(需要 git + 網路)" & return & ¬
					"B) 手動指定路徑" buttons {"取消", "B 手動指定", "A 自動 clone"} default button "A 自動 clone"
				if button returned of userChoice is "取消" then return
				if button returned of userChoice is "A 自動 clone" then
					display dialog "正在 clone · 視網路速度約 1-3 分鐘 ..." giving up after 1
					do shell script "cd $HOME && git clone https://github.com/Sterio068/company-ai-workspace.git ChengFu 2>&1"
					set repoPath to (do shell script "echo $HOME/ChengFu")
				else
					set repoChoice to choose folder with prompt "選 ChengFu repo 根目錄(含 config-templates/)"
					set repoPath to POSIX path of repoChoice
					set repoPath to do shell script "echo " & quoted form of repoPath & " | sed 's:/$::'"
				end if
			end if
		end if
		on error errMsg
			display dialog "找 repo 失敗:" & errMsg buttons {"關閉"} with icon stop
			return
		end try

		-- 若從 .dmg 執行,記下內建新版 source 快照。既有安裝也會在 installer-run.command 先套新版程式碼,但保留 .env/data/uploads。
		set appBundlePath to POSIX path of (path to me)
		set sourceTgzPath to do shell script "
APP_BUNDLE=" & quoted form of appBundlePath & "
APP_PARENT=$(dirname \"$APP_BUNDLE\")
SOURCE_TGZ=\"$APP_PARENT/ChengFu-source.tar.gz\"
if [[ -f \"$SOURCE_TGZ\" ]]; then
  printf %s \"$SOURCE_TGZ\"
fi
"

	-- ============ 步驟 1.5 · 偵測既有安裝資料 ============
	set reuseExisting to false
	set envFilePath to repoPath & "/config-templates/.env"
	set openaiKey to ""
	set anthropicKey to ""
	set publicDomain to ""
		set adminEmail to ""
	set adminPassword to ""
	set adminName to "承富管理員"
	set nasPath to ""
	set hasExistingEnv to do shell script "test -s " & quoted form of envFilePath & " && echo YES || echo NO"
	set hasOpenAIKey to do shell script "security find-generic-password -s 'chengfu-ai-openai-key' -w >/dev/null 2>&1 && echo YES || echo NO"
	set hasAnthropicKey to do shell script "security find-generic-password -s 'chengfu-ai-anthropic-key' -w >/dev/null 2>&1 && echo YES || echo NO"
	set existingDomain to ""
	set existingAdminEmail to ""
	set existingKnowledgeRoots to ""
	if hasExistingEnv is "YES" then
		set existingAdminEmail to do shell script "awk -F= '$1==\"ADMIN_EMAIL\"{print substr($0,index($0,\"=\")+1); exit}' " & quoted form of envFilePath
		set existingDomain to do shell script "awk -F= '$1==\"DOMAIN_CLIENT\"{print substr($0,index($0,\"=\")+1); exit}' " & quoted form of envFilePath
		set existingKnowledgeRoots to do shell script "awk -F= '$1==\"KNOWLEDGE_ALLOWED_ROOTS\"{print substr($0,index($0,\"=\")+1); exit}' " & quoted form of envFilePath
		if existingAdminEmail is not "" then set adminEmail to existingAdminEmail
		if existingDomain starts with "https://" then set publicDomain to text 9 thru -1 of existingDomain
		if existingKnowledgeRoots is not "" then
			set nasPath to do shell script "printf %s " & quoted form of existingKnowledgeRoots & " | awk -F, '{print $1}'"
			if nasPath is "/Volumes" or nasPath is "/data" or nasPath is "/tmp/chengfu-test-sources" then set nasPath to ""
		end if
	end if

	if hasExistingEnv is "YES" and hasOpenAIKey is "YES" then
		set claudeReuseLine to "  • Claude 備援 Keychain:" & hasAnthropicKey
		set reuseChoice to display dialog "偵測到既有安裝資料,要直接沿用嗎?" & return & return & ¬
			"  • Repo:" & repoPath & return & ¬
			"  • .env:YES" & return & ¬
			"  • OpenAI Keychain:YES" & return & ¬
			claudeReuseLine & return & ¬
			"  • 管理員 email:" & adminEmail & return & ¬
			"  • 入口:" & existingDomain & return & return & ¬
			"選「沿用既有」會保留原本 API Key、域名、Mongo 帳號、對話與 Agent,不再要求重填。" & return & ¬
			"若要換 API Key / admin / 網域,選「重新設定」。" ¬
			with title "承富 AI 安裝 · 偵測到既有資料" buttons {"取消", "重新設定", "沿用既有"} default button "沿用既有" with icon note
		if button returned of reuseChoice is "取消" then return
		if button returned of reuseChoice is "沿用既有" then set reuseExisting to true
	end if

	-- ============ 步驟 2 · 收集 .env 機密 ============
	if reuseExisting is false then
	-- 2a · OpenAI API Key(主力)
	repeat
		set apiKeyDialog to display dialog ¬
			"請貼上 OpenAI API Key" & return & return & ¬
			"用途:主力 AI 引擎(GPT-5.5)" & return & ¬
			"格式:sk-..." & return & return & ¬
			"取得網址:" & return & ¬
			"https://platform.openai.com/api-keys" & return & return & ¬
			"若還沒有 key,請按「打開取得網址」,登入 OpenAI Platform 後建立 API key。" & return & return & ¬
			"⚠️ 此值會存進 macOS Keychain · 不會明文寫進 .env" ¬
			default answer openaiKey with title "承富 AI 安裝 · 1/7 · OpenAI API Key" with hidden answer buttons {"取消", "打開取得網址", "下一步"} default button "下一步"
		if button returned of apiKeyDialog is "取消" then return
		set openaiKey to text returned of apiKeyDialog
		if button returned of apiKeyDialog is "打開取得網址" then
			open location "https://platform.openai.com/api-keys"
		else
			exit repeat
		end if
	end repeat
	if length of openaiKey is less than 20 then
		display dialog "❌ API Key 太短 · 請確認是完整 sk-... 格式" buttons {"關閉"} with icon stop
		return
	end if

	-- 2a-2 · Anthropic API Key(選配備援)
	repeat
		set anthropicKeyDialog to display dialog ¬
			"請貼上 Anthropic API Key(選配 · Claude 備援)" & return & return & ¬
			"用途:Claude 備援 / 長文件工作流" & return & ¬
			"格式:sk-ant-..." & return & return & ¬
			"取得網址:" & return & ¬
			"https://console.anthropic.com/settings/keys" & return & return & ¬
			"留空可跳過 · 之後仍可在 Keychain 補設" ¬
			default answer anthropicKey with title "承富 AI 安裝 · 2/7 · Anthropic API Key" with hidden answer buttons {"取消", "打開取得網址", "下一步"} default button "下一步"
		if button returned of anthropicKeyDialog is "取消" then return
		set anthropicKey to text returned of anthropicKeyDialog
		if button returned of anthropicKeyDialog is "打開取得網址" then
			open location "https://console.anthropic.com/settings/keys"
		else
			exit repeat
		end if
	end repeat

	-- 2b · 公司域名(對外)· 暫時可空
	set domainDialog to display dialog ¬
		"請輸入承富對外域名(可暫時跳過 · 用本機 localhost)" & return & return & ¬
		"例:ai.chengfu.com.tw" & return & ¬
		"留空 → 本機安全模式(localhost · production) · 之後可手動改 .env" ¬
		default answer publicDomain with title "承富 AI 安裝 · 3/6" buttons {"取消", "下一步"} default button "下一步"
	if button returned of domainDialog is "取消" then return
	set publicDomain to text returned of domainDialog

	-- 2c · 管理員 email
		set adminDialog to display dialog ¬
			"請輸入承富 AI 管理員 email" & return & return & ¬
			"將用此 email 自動註冊 LibreChat 第一個 admin 帳號" & return & ¬
			"請使用承富公司管理信箱；此欄位不可留空" ¬
			default answer adminEmail with title "承富 AI 安裝 · 4/7" buttons {"取消", "下一步"} default button "下一步"
		if button returned of adminDialog is "取消" then return
		set adminEmail to text returned of adminDialog
		if adminEmail is "" or adminEmail does not contain "@" then
			display dialog "❌ 管理員 email 不可空白,且必須是有效 email" buttons {"關閉"} with icon stop
			return
		end if

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
		default answer nasPath with title "承富 AI 安裝 · 7/7" buttons {"取消", "下一步"} default button "下一步"
	if button returned of nasDialog is "取消" then return
	set nasPath to text returned of nasDialog
	end if

	-- 2e · 確認啟動
	set domainDisplay to publicDomain
	if publicDomain is "" then set domainDisplay to "(本機 only · localhost)"
	set nasDisplay to nasPath
	if nasPath is "" then set nasDisplay to "(本機 /tmp 測試)"
	set claudeDisplay to "已收(隱藏)"
	set openaiDisplay to "已收(隱藏)"
	set modeDisplay to "重新設定"
	if reuseExisting then
		set modeDisplay to "沿用既有資料"
		set openaiDisplay to "沿用 Keychain(隱藏)"
		if hasAnthropicKey is "YES" then
			set claudeDisplay to "沿用 Keychain(隱藏)"
		else
			set claudeDisplay to "未設定"
		end if
	else if anthropicKey is "" then
		set claudeDisplay to "未設定"
	end if

	set confirmText to "已收集設定 · 確認啟動?" & return & return & ¬
		"• 模式:" & modeDisplay & return & ¬
		"• Repo 路徑:" & repoPath & return & ¬
		"• OpenAI Key:" & openaiDisplay & return & ¬
		"• Claude 備援:" & claudeDisplay & return & ¬
		"• 對外域名:" & domainDisplay & return & ¬
		"• 管理員 email:" & adminEmail & return & ¬
		"• NAS 路徑:" & nasDisplay & return & return & ¬
		"按「啟動安裝」會:" & return & ¬
		"  1. 寫入或沿用 macOS Keychain" & return & ¬
		"  2. 建立或沿用 .env · 保留既有 Mongo 資料" & return & ¬
		"  3. 抓 5 個 Docker image(LibreChat / Mongo / Meili / nginx / accounting)" & return & ¬
		"  4. 啟動 6 容器 · 等 healthy" & return & ¬
		"  5. 跑 smoke test · 印維運手冊"
	display dialog confirmText with title "承富 AI 安裝 · 7/7 確認" buttons {"上一步取消", "啟動安裝"} default button "啟動安裝"

	-- ============ 步驟 3 · 寫 Keychain + .env ============
	-- 用 do shell script · 隱藏終端機
	try
		if reuseExisting is false then
			do shell script ¬
				"security delete-generic-password -s 'chengfu-ai-openai-key' 2>/dev/null; " & ¬
				"security add-generic-password -a $USER -s 'chengfu-ai-openai-key' -w " & quoted form of openaiKey & " 2>&1"
			if anthropicKey is not "" and length of anthropicKey > 10 then
				do shell script ¬
					"security delete-generic-password -s 'chengfu-ai-anthropic-key' 2>/dev/null; " & ¬
					"security add-generic-password -a $USER -s 'chengfu-ai-anthropic-key' -w " & quoted form of anthropicKey & " 2>&1"
			end if
			-- admin 密碼只給本次安裝建立帳號 / Agent 用,不寫進 installer-run.command 明文。
			do shell script ¬
				"security delete-generic-password -s 'chengfu-ai-admin-install-password' 2>/dev/null; " & ¬
				"security add-generic-password -a $USER -s 'chengfu-ai-admin-install-password' -w " & quoted form of adminPassword & " 2>&1"
		else
			do shell script "security find-generic-password -s 'chengfu-ai-openai-key' -w >/dev/null 2>&1"
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
	if reuseExisting then
		-- 沿用既有 .env,只做 CR→LF 正規化,避免 Docker Compose 讀不到後續 env。
		do shell script "/usr/bin/perl -0pi -e 's/\\x0d/\\x0a/g' " & quoted form of envFilePath
	else
		-- 交付安裝永遠使用 production 安全模式。
		-- 是否填公司域名只影響 DOMAIN_CLIENT / DOMAIN_SERVER,不可降級為 development 或開 legacy header。
		set envMode to "production"
		set envLegacy to "0"
		set envDomain to "http://localhost"
		if publicDomain is not "" then
			set envDomain to "https://" & publicDomain
		end if

		set envKnowledge to "/Volumes,/data,/tmp/chengfu-test-sources"
		if nasPath is not "" then set envKnowledge to nasPath & ",/Volumes,/data"

		set envContent to "# 承富 AI v1.3/vNext · 自動產自 ChengFu-AI-Installer.app · 2026-04-24" & return & ¬
			"NODE_ENV=" & envMode & return & ¬
			"ECC_ENV=" & envMode & return & ¬
			"ALLOW_LEGACY_AUTH_HEADERS=" & envLegacy & return & ¬
			"DOMAIN_CLIENT=" & envDomain & return & ¬
			"DOMAIN_SERVER=" & envDomain & return & ¬
			"ADMIN_EMAIL=" & adminEmail & return & ¬
			"ADMIN_EMAILS=" & adminEmail & return & ¬
			"ALLOW_REGISTRATION=false" & return & ¬
			"OPENAI_MODELS=gpt-5.4,gpt-5.4-mini,gpt-5.4-nano" & return & ¬
			"ANTHROPIC_MODELS=claude-opus-4-7,claude-sonnet-4-6,claude-haiku-4-5" & return & ¬
			"CHENGFU_DEFAULT_AI_PROVIDER=openai" & return & ¬
			"MONGO_URI=mongodb://mongodb:27017/chengfu" & return & ¬
			"SEARCH=true" & return & ¬
			"MEILI_HOST=http://meilisearch:7700" & return & ¬
			"KNOWLEDGE_ALLOWED_ROOTS=" & envKnowledge & return

		-- AppleScript 的 return 是 CR,寫 .env 前統一轉 LF,避免 Docker Compose 讀不到後續 env。
		-- 用 Perl hex escape 避開 macOS tr / AppleScript 雙層跳脫造成的字面值問題。
		do shell script "printf %s " & quoted form of envContent & " | /usr/bin/perl -pe 's/\\x0d/\\x0a/g' > " & quoted form of envFilePath
	end if

	-- ============ 步驟 4 · 開 Terminal 跑 docker compose(讓 IT 看到進度)============
	-- v1.3.0 dry-run fix · 原本 `tell application "Terminal"` 在 macOS Sequoia+ 需要
	-- AppleEvent 授權 · unsigned .app 會 -1743 錯
	-- 改用 `open -a Terminal` 打開 .command 檔 · 不需 AppleEvent 授權
	set scriptPath to repoPath & "/scripts/start.sh"
	set commandFile to repoPath & "/installer-run.command"
	set reuseShellFlag to "0"
	if reuseExisting then set reuseShellFlag to "1"
	set finalPasswordLine to "    密碼:你剛在精靈 5/7 步驟設的"
	if reuseExisting then set finalPasswordLine to "    密碼:沿用原本登入密碼"
	set finalDialogLoginLine to "  1. 點「開啟 Launcher」 · 用剛設的 " & adminEmail & " 登入"
	if reuseExisting then set finalDialogLoginLine to "  1. 點「開啟 Launcher」 · 用原本帳號登入(" & adminEmail & ")"

	-- 寫可執行 .command 檔 · Terminal 雙擊會跑
	-- v1.3.0 · 自動建 LibreChat admin(用戶剛設的 email + 密碼)
	-- 用 LibreChat 內建 npm run create-user CLI
	-- v1.3.0+ · 加完整 log + timeout · 避免 silent fail 後用戶看不出原因
		set cmdContent to "#!/bin/bash
set -euo pipefail
export PATH=/opt/homebrew/bin:/usr/local/bin:/Applications/Docker.app/Contents/Resources/bin:$PATH
# v1.3.0+ · 所有輸出同步寫 log · 事後可診斷
LOG_FILE=/tmp/chengfu-install.log
STATUS_FILE=/tmp/chengfu-install.status
: > \"$LOG_FILE\"
rm -f \"$STATUS_FILE\"
exec > >(tee -a \"$LOG_FILE\") 2>&1
	echo \"=== 承富 AI 安裝 · $(date) ===\"
	cd " & quoted form of repoPath & "
	BUNDLED_SOURCE_TGZ=" & quoted form of sourceTgzPath & "
	if [[ -f \"$BUNDLED_SOURCE_TGZ\" ]]; then
	  echo '═══ [0/6] 套用 DMG 內建新版程式碼(保留 .env / data / uploads) ═══'
	  TMP_SRC=$(mktemp -d /tmp/chengfu-source.XXXXXX)
	  tar -xzf \"$BUNDLED_SOURCE_TGZ\" -C \"$TMP_SRC\"
	  rsync -a \
	    --exclude='.git/' \
	    --exclude='.claude/' \
	    --exclude='config-templates/.env' \
	    --exclude='config-templates/data/' \
	    --exclude='config-templates/data-sandbox/' \
	    --exclude='config-templates/logs/' \
	    --exclude='config-templates/uploads/' \
	    --exclude='config-templates/images/' \
	    --exclude='frontend/launcher/node_modules/' \
	    --exclude='tests/e2e/node_modules/' \
	    --exclude='tests/e2e/test-results/' \
	    --exclude='tests/e2e/playwright-report/' \
	    --exclude='installer/dist/' \
	    --exclude='installer-run.command' \
	    \"$TMP_SRC\"/ ./
	  rm -rf \"$TMP_SRC\"
	  echo '✓ 已套用新版程式碼 · 既有設定與資料保留'
	fi
	ADMIN_EMAIL=" & quoted form of adminEmail & "
ADMIN_NAME=" & quoted form of adminName & "
REUSE_EXISTING_INSTALL=" & quoted form of reuseShellFlag & "
ADMIN_PASSWORD=\"\"
if [ \"$REUSE_EXISTING_INSTALL\" != '1' ]; then
  ADMIN_PASSWORD=$(security find-generic-password -s 'chengfu-ai-admin-install-password' -w 2>/dev/null || true)
fi
cleanup_install_secret() {
  security delete-generic-password -s 'chengfu-ai-admin-install-password' >/dev/null 2>&1 || true
}
finish_install() {
  local rc=$?
  if [ $rc -eq 0 ]; then echo OK > \"$STATUS_FILE\"; else echo FAIL > \"$STATUS_FILE\"; fi
  cleanup_install_secret
  exit $rc
}
trap finish_install EXIT
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
echo \"═══ [3/6] 檢查 / 建立 admin 帳號($ADMIN_EMAIL) ═══\"
USER_COUNT=$(docker exec chengfu-mongo mongosh chengfu --quiet --eval 'db.users.countDocuments()' 2>/dev/null | tr -d '[:space:]')
if [ -z \"$USER_COUNT\" ]; then USER_COUNT=0; fi
if [ -n \"$ADMIN_PASSWORD\" ]; then
  # LibreChat npm run create-user 會問 confirm · echo y 自動過
  # user 已存在會報錯但不致命 · continue 下一步(v1.3.0 fix)
  docker exec chengfu-librechat sh -c 'echo y | npm run create-user -- \"$1\" \"$2\" \"$3\" \"$4\"' sh \"$ADMIN_EMAIL\" \"$ADMIN_NAME\" \"$ADMIN_EMAIL\" \"$ADMIN_PASSWORD\" 2>&1 | tail -10
else
  echo '✓ 沿用既有安裝資料 · 不重新建立 admin 帳號'
fi
echo ''
echo '═══ [4/6] 等 admin / 既有使用者 ready (max 30s) ═══'
ADMIN_READY=0
TIMEOUT=15
while [ $TIMEOUT -gt 0 ]; do
  COUNT=$(docker exec chengfu-mongo mongosh chengfu --quiet --eval 'db.users.countDocuments()' 2>/dev/null | tr -d '[:space:]')
  if [ \"$COUNT\" != '0' ] && [ -n \"$COUNT\" ]; then
    echo \"✓ 使用者資料 ready (COUNT=$COUNT)\"
    ADMIN_READY=1
    break
  fi
  echo \"  等使用者寫入... (COUNT=$COUNT)\"
  sleep 2
  TIMEOUT=$((TIMEOUT - 1))
done
if [ $ADMIN_READY -ne 1 ]; then
  echo '⚠ 找不到既有使用者,且本次沒有 admin 密碼可建立帳號。'
  echo '   若這是全新機器 / Mongo volume 已被清空,請重跑安裝精靈並選「重新設定」。'
  echo '   log 在 /tmp/chengfu-install.log'
fi
echo ''
echo '═══ [5/6] 檢查 / 建 10 個 core Agent ═══'
echo '(✨ 主管家 · 🎯 投標 · 🎪 活動 · 🎨 設計 · 📣 公關 · 🎙 會議 · 📚 知識 · 💰 財務 · ⚖️ 法務 · 📊 營運)'
PROVIDER_MODE=openai
DESIRED_AGENT_COUNT=10
if security find-generic-password -s 'chengfu-ai-anthropic-key' -w >/dev/null 2>&1; then
  PROVIDER_MODE=both
  DESIRED_AGENT_COUNT=20
fi
AGENT_COUNT=$(docker exec chengfu-mongo mongosh chengfu --quiet --eval 'db.agents.countDocuments()' 2>/dev/null | tr -d '[:space:]')
if [ -z \"$AGENT_COUNT\" ]; then AGENT_COUNT=0; fi
echo \"AI provider 建立模式: $PROVIDER_MODE · 目前 Agent: $AGENT_COUNT / 目標: $DESIRED_AGENT_COUNT\"
if [ \"$AGENT_COUNT\" -ge \"$DESIRED_AGENT_COUNT\" ]; then
  echo '✓ 既有 Agent 已足夠 · 跳過重建'
elif [ $ADMIN_READY -eq 1 ] && [ -n \"$ADMIN_PASSWORD\" ]; then
  # LIBRECHAT_URL=http://localhost(走 nginx · 不直連 3080 因 docker 網路只內部)
  LIBRECHAT_URL=http://localhost \\
  LIBRECHAT_ADMIN_EMAIL=\"$ADMIN_EMAIL\" \\
  LIBRECHAT_ADMIN_PASSWORD=\"$ADMIN_PASSWORD\" \\
  python3 scripts/create-agents.py --tier core --provider \"$PROVIDER_MODE\" 2>&1 | tee -a \"$LOG_FILE\"
  AGENT_RC=${PIPESTATUS[0]}
	  if [ $AGENT_RC -ne 0 ]; then
	    echo '⚠ Agent 建立失敗 (rc=' $AGENT_RC ') · 手動跑:'
    echo '   LIBRECHAT_URL=http://localhost \\\\'
    echo \"   LIBRECHAT_ADMIN_EMAIL=$ADMIN_EMAIL \\\\\"
	    echo '   LIBRECHAT_ADMIN_PASSWORD=<密碼> \\\\'
	    echo '   python3 scripts/create-agents.py --tier core --provider both'
	    exit 1
	  fi
	else
	  echo '⚠ Agent 不足,但本次沿用模式沒有 admin 密碼可登入 LibreChat 建立 Agent。'
	  echo '   請重跑安裝精靈並選「重新設定」,或手動執行 scripts/create-agents.py。'
	  exit 1
	fi
echo ''
echo '═══ [6/6] smoke test ═══'
echo ''
if [ -n \"$ADMIN_PASSWORD\" ]; then
  LIBRECHAT_ADMIN_EMAIL=\"$ADMIN_EMAIL\" LIBRECHAT_ADMIN_PASSWORD=\"$ADMIN_PASSWORD\" bash scripts/smoke-test.sh
else
  bash scripts/smoke-test.sh
fi
echo ''
echo '✅ 安裝完成 · admin / 職能助手已確認'
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
echo '" & finalPasswordLine & "'
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

		-- 等 Terminal 安裝腳本回報 OK / FAIL；不要只看 nginx /healthz 靜態頁。
		delay 10
		set installStatus to do shell script "cat /tmp/chengfu-install.status 2>/dev/null || echo WAIT"
		set retries to 0
		repeat while installStatus is "WAIT" and retries < 90
			delay 5
			set installStatus to do shell script "cat /tmp/chengfu-install.status 2>/dev/null || echo WAIT"
			set retries to retries + 1
		end repeat

		-- ============ 步驟 5 · 印維運手冊 ============
		if installStatus is "OK" then
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
			finalDialogLoginLine & return & ¬
			"  2. 按 ⌘U 進「同仁管理」 · 建其他 9 位同仁" & return & ¬
			"  3. 選 7 個頭銜 preset · 或自訂權限勾選" & return & ¬
			"  4. 每個同仁產隨機密碼 · 複製分發" & return & return & ¬
			"提醒同事:" & return & ¬
			"  • iPhone 場勘:設定 → 相機 → 格式 → 最相容(JPEG)" & return & ¬
			"  • 使用教學(⌘?)· 13 份中文手冊" & return & return & ¬
				"問題找:承富內部 IT / 專案管理員" ¬
			with title "✅ 安裝完成" buttons {"開啟 Launcher", "稍後"} default button "開啟 Launcher"
		if button returned of result is "開啟 Launcher" then
			do shell script "open http://localhost/"
		end if
		else
			display dialog "⚠️ 安裝尚未通過交付 smoke test" & return & return & ¬
				"看 Terminal 視窗或 log 確認失敗原因:" & return & ¬
				"  /tmp/chengfu-install.log" & return & ¬
				"或跑:" & return & ¬
				"  cd " & repoPath & return & ¬
				"  ./scripts/smoke-test.sh" & return & return & ¬
				"問題找:承富內部 IT / 專案管理員" with title "⚠️ 部分完成" buttons {"關閉"} with icon caution
	end if
end run
