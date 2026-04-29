#Requires -Version 5.1
<#
企業 AI 工作台 · Windows 一行安裝

建議指令:
  powershell -ExecutionPolicy Bypass -NoProfile -Command "irm https://raw.githubusercontent.com/Sterio068/company-ai-workspace/main/installer/install.ps1 | iex"

自訂:
  $env:INSTALL_DIR="$env:USERPROFILE\CompanyAIWorkspace"; powershell -ExecutionPolicy Bypass -File .\installer\install.ps1
#>

[CmdletBinding()]
param(
    [string]$RepoUrl,
    [string]$InstallDir,
    [string]$Branch,
    [switch]$NonInteractive,
    [switch]$NoOpen
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = "Stop"

if ([System.Environment]::OSVersion.Platform -ne [System.PlatformID]::Win32NT) {
    throw "install.ps1 僅支援 Windows。macOS 請用 installer/install.sh。"
}

if ([string]::IsNullOrWhiteSpace($RepoUrl)) { $RepoUrl = if ($env:REPO_URL) { $env:REPO_URL } else { "https://github.com/Sterio068/company-ai-workspace.git" } }
if ([string]::IsNullOrWhiteSpace($InstallDir)) { $InstallDir = if ($env:INSTALL_DIR) { $env:INSTALL_DIR } else { Join-Path $env:USERPROFILE "CompanyAIWorkspace" } }
if ([string]::IsNullOrWhiteSpace($Branch)) { $Branch = if ($env:BRANCH) { $env:BRANCH } else { "main" } }
if ($env:NONINTERACTIVE -eq "1") { $NonInteractive = $true }

$AutoInstallDocker = $env:AUTO_INSTALL_DOCKER -ne "0"

function Write-Ok { param([string]$Text) Write-Host "  ✓ $Text" -ForegroundColor Green }
function Write-WarnLine { param([string]$Text) Write-Host "  ⚠ $Text" -ForegroundColor Yellow }
function Write-Step { param([string]$Text) Write-Host ""; Write-Host "━━━ $Text ━━━" -ForegroundColor Cyan }

function Confirm-Yes {
    param([string]$Prompt)
    if ($NonInteractive) { return $false }
    $answer = Read-Host "  $Prompt (Y/n)"
    return [string]::IsNullOrWhiteSpace($answer) -or $answer -match '^(y|yes|Y|YES)$'
}

function Add-CommonToolPaths {
    $paths = @(
        "$env:ProgramFiles\Git\cmd",
        "$env:ProgramFiles\Docker\Docker\resources\bin",
        "$env:ProgramFiles\Docker\Docker"
    )
    foreach ($path in $paths) {
        if ((Test-Path -LiteralPath $path) -and ($env:Path -notlike "*$path*")) {
            $env:Path = "$path;$env:Path"
        }
    }
}

function Ensure-Winget {
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        return
    }
    throw "找不到 winget。請先從 Microsoft Store 安裝 App Installer,或手動安裝 Git / Docker Desktop。"
}

function Ensure-Git {
    Add-CommonToolPaths
    if (Get-Command git -ErrorAction SilentlyContinue) {
        Write-Ok "git $((& git --version) -replace 'git version ', '')"
        return
    }

    if ($NonInteractive -or -not (Confirm-Yes "找不到 Git · 要用 winget 自動安裝嗎?")) {
        throw "找不到 Git。手動下載: https://git-scm.com/download/win"
    }

    Ensure-Winget
    & winget install -e --id Git.Git --accept-package-agreements --accept-source-agreements
    if ($LASTEXITCODE -ne 0) { throw "Git 安裝失敗" }
    Add-CommonToolPaths
    if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
        throw "Git 已安裝但目前 PowerShell 找不到 git。請關掉視窗重開後再跑。"
    }
    Write-Ok "git $((& git --version) -replace 'git version ', '')"
}

function Wait-DockerDaemon {
    param([int]$MaxSeconds = 300)
    $elapsed = 0
    while ($elapsed -lt $MaxSeconds) {
        Add-CommonToolPaths
        & docker info *> $null
        if ($LASTEXITCODE -eq 0) {
            Write-Ok "docker daemon · running"
            return $true
        }
        Start-Sleep -Seconds 5
        $elapsed += 5
        Write-Host "." -NoNewline
    }
    Write-Host ""
    return $false
}

function Ensure-DockerDesktop {
    Add-CommonToolPaths
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        if (-not $AutoInstallDocker -or $NonInteractive -or -not (Confirm-Yes "找不到 Docker Desktop · 要用 winget 自動安裝嗎?")) {
            throw "找不到 Docker Desktop。手動下載: https://www.docker.com/products/docker-desktop/"
        }
        Ensure-Winget
        & winget install -e --id Docker.DockerDesktop --accept-package-agreements --accept-source-agreements
        if ($LASTEXITCODE -ne 0) { throw "Docker Desktop 安裝失敗" }
        Add-CommonToolPaths
    }

    if (Get-Command docker -ErrorAction SilentlyContinue) {
        Write-Ok "docker $((& docker --version) -replace 'Docker version ', '')"
    }

    & docker info *> $null
    if ($LASTEXITCODE -eq 0) {
        Write-Ok "docker daemon · running"
        return
    }

    Write-Host "  · 啟動 Docker Desktop · 第一次開啟請完成畫面上的 WSL2/授權提示..."
    $dockerDesktopPaths = @(
        "$env:ProgramFiles\Docker\Docker\Docker Desktop.exe",
        "${env:ProgramFiles(x86)}\Docker\Docker\Docker Desktop.exe"
    )
    $dockerDesktop = $dockerDesktopPaths | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
    if ($dockerDesktop) {
        Start-Process -FilePath $dockerDesktop | Out-Null
    }

    Write-Host "  · 等 Docker daemon 啟動(最多 5 分鐘)" -NoNewline
    if (-not (Wait-DockerDaemon -MaxSeconds 300)) {
        throw "Docker daemon 沒啟動。若剛安裝 Docker Desktop,請完成初始化或重新開機後重跑此指令。"
    }
}

function Read-PlainSecret {
    param([string]$Prompt)
    $secure = Read-Host "  $Prompt" -AsSecureString
    return (ConvertTo-CompanyAIPlainText -SecureString $secure)
}

function Read-PasswordTwice {
    param([string]$Prompt)
    while ($true) {
        $first = Read-PlainSecret -Prompt $Prompt
        $second = Read-PlainSecret -Prompt "再輸入一次確認"
        if ($first -ne $second) {
            Write-WarnLine "兩次密碼不一致,請重試"
            continue
        }
        if ($first.Length -lt 8) {
            Write-WarnLine "密碼至少 8 字"
            continue
        }
        return $first
    }
}

function Set-EnvValue {
    param(
        [Parameter(Mandatory = $true)][string]$File,
        [Parameter(Mandatory = $true)][string]$Key,
        [Parameter(Mandatory = $true)][string]$Value
    )

    $lines = @()
    if (Test-Path -LiteralPath $File) {
        $lines = @(Get-Content -LiteralPath $File)
    }

    $found = $false
    $escapedKey = [regex]::Escape($Key)
    $output = foreach ($line in $lines) {
        if ($line -match "^\s*$escapedKey=") {
            $found = $true
            "$Key=$Value"
        }
        else {
            $line
        }
    }
    if (-not $found) {
        $output += "$Key=$Value"
    }
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllLines($File, [string[]]$output, $utf8NoBom)
}

function Prompt-ApiSecretIfMissing {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$Label,
        [Parameter(Mandatory = $true)][string]$Url,
        [string]$EnvName,
        [switch]$Required
    )

    if (Test-CompanyAISecret -Name $Name) {
        Write-Ok "$Label 已存在 · 跳過"
        return
    }

    if ($EnvName -and -not [string]::IsNullOrWhiteSpace([Environment]::GetEnvironmentVariable($EnvName))) {
        Set-CompanyAISecret -Name $Name -Value ([Environment]::GetEnvironmentVariable($EnvName))
        Write-Ok "$Label 已從環境變數寫入"
        return
    }

    if ($NonInteractive) {
        if ($Required) { throw "NONINTERACTIVE=1 但缺少 $EnvName" }
        return
    }

    Write-Host "  $Label 取得網址: $Url"
    Write-Host "  可另開瀏覽器: start $Url"
    $value = Read-PlainSecret -Prompt "貼入 $Label"
    if ([string]::IsNullOrWhiteSpace($value)) {
        if ($Required) { throw "$Label 不可為空" }
        Write-WarnLine "$Label 已略過"
        return
    }
    Set-CompanyAISecret -Name $Name -Value $value
    Write-Ok "$Label 已加密保存"
}

try {
    Clear-Host
}
catch {}

Write-Host ""
Write-Host "═══════════════════════════════════════════════════"
Write-Host "  企業 AI 工作台 · Windows 一行安裝(含 Docker Desktop)"
Write-Host "═══════════════════════════════════════════════════"
Write-Host ""
Write-Host "  目標路徑: $InstallDir"
Write-Host "  Repo:    $RepoUrl"
Write-Host "  Branch:  $Branch"
Write-Host ""

if (-not $NonInteractive) {
    Read-Host "  按 Enter 開始 · 或 Ctrl+C 取消" | Out-Null
}

Write-Step "1/6 · 環境預檢"
Ensure-Git
Ensure-DockerDesktop

try {
    $ramBytes = (Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory
    $ramGb = [math]::Round($ramBytes / 1GB)
    if ($ramGb -lt 16) {
        Write-WarnLine "RAM ${ramGb}GB · 建議 ≥ 16GB"
    }
    else {
        Write-Ok "RAM ${ramGb}GB"
    }
}
catch {
    Write-WarnLine "無法讀取 RAM 資訊 · 略過"
}

Write-Step "2/6 · 拉程式碼到 $InstallDir"

if (Test-Path -LiteralPath (Join-Path $InstallDir ".git")) {
    Push-Location $InstallDir
    try {
        $before = (& git rev-parse HEAD).Trim()
        & git fetch origin $Branch --quiet
        & git pull --ff-only origin $Branch --quiet
        if ($LASTEXITCODE -ne 0) { throw "git pull 失敗" }
        $after = (& git rev-parse HEAD).Trim()
        if ($before -ne $after) {
            Write-Ok "已 pull · $($before.Substring(0,7)) → $($after.Substring(0,7))"
        }
        else {
            Write-Ok "已是最新 · $($after.Substring(0,7))"
        }
    }
    finally {
        Pop-Location
    }
}
else {
    if (Test-Path -LiteralPath $InstallDir) {
        throw "$InstallDir 存在但不是 git repo。請先改名或移走。"
    }
    & git clone --depth 100 --branch $Branch --quiet $RepoUrl $InstallDir
    if ($LASTEXITCODE -ne 0) { throw "git clone 失敗" }
    $sha = (& git -C $InstallDir rev-parse --short HEAD).Trim()
    Write-Ok "clone 完成 · $sha"
}

. (Join-Path $InstallDir "scripts\windows-secrets.ps1")
Initialize-CompanyAISecretStore -ProjectDir $InstallDir -ServicePrefix "company-ai"

Write-Step "3/6 · 設定 API keys 與第一位管理員(Windows DPAPI 加密保存)"

Prompt-ApiSecretIfMissing -Name "openai-key" -Label "OpenAI API Key(必要 · 主力 AI)" -Url "https://platform.openai.com/api-keys" -EnvName "INSTALL_OPENAI_API_KEY" -Required
Prompt-ApiSecretIfMissing -Name "anthropic-key" -Label "Anthropic API Key(選配 · Claude 備援)" -Url "https://console.anthropic.com/settings/keys" -EnvName "INSTALL_ANTHROPIC_API_KEY"
Prompt-ApiSecretIfMissing -Name "notebooklm-access-token" -Label "NotebookLM Enterprise Access Token(選配)" -Url "https://docs.cloud.google.com/gemini/enterprise/notebooklm-enterprise/docs/api-notebooks" -EnvName "INSTALL_NOTEBOOKLM_ACCESS_TOKEN"

if ((Test-CompanyAISecret -Name "admin-install-email") -and (Test-CompanyAISecret -Name "admin-install-password")) {
    Write-Ok "第一位管理員憑證已存在 · 跳過"
}
else {
    if ($env:INSTALL_ADMIN_EMAIL -and $env:INSTALL_ADMIN_PASSWORD) {
        Set-CompanyAISecret -Name "admin-install-email" -Value $env:INSTALL_ADMIN_EMAIL
        Set-CompanyAISecret -Name "admin-install-password" -Value $env:INSTALL_ADMIN_PASSWORD
        Write-Ok "第一位管理員已從環境變數寫入"
    }
    elseif ($NonInteractive) {
        throw "NONINTERACTIVE=1 但缺少 INSTALL_ADMIN_EMAIL / INSTALL_ADMIN_PASSWORD"
    }
    else {
        Write-Host "  · 設定第一次登入用的管理員帳號"
        $adminEmail = Read-Host "  管理員 Email [admin@company-ai.local]"
        if ([string]::IsNullOrWhiteSpace($adminEmail)) { $adminEmail = "admin@company-ai.local" }
        if ($adminEmail -notmatch ".+@.+") { throw "管理員 Email 格式不正確" }
        $adminPassword = Read-PasswordTwice -Prompt "管理員登入密碼"
        Set-CompanyAISecret -Name "admin-install-email" -Value $adminEmail
        Set-CompanyAISecret -Name "admin-install-password" -Value $adminPassword
        Write-Ok "第一位管理員憑證已加密保存"
    }
}

Ensure-CompanyAIGeneratedSecret -Name "jwt-secret" -Bytes 32
Ensure-CompanyAIGeneratedSecret -Name "jwt-refresh-secret" -Bytes 32
Ensure-CompanyAIGeneratedSecret -Name "creds-key" -Bytes 32
Ensure-CompanyAIGeneratedSecret -Name "creds-iv" -Bytes 16
Ensure-CompanyAIGeneratedSecret -Name "meili-master-key" -Bytes 32
Ensure-CompanyAIGeneratedSecret -Name "internal-token" -Bytes 32
Ensure-CompanyAIGeneratedSecret -Name "action-bridge-token" -Bytes 32
Write-Ok "JWT / CREDS / Meili / Internal tokens 已準備"

Write-Step "4/6 · 建立 .env 並啟動 Docker 容器"

$envFile = Join-Path $InstallDir "config-templates\.env"
$envExample = Join-Path $InstallDir "config-templates\.env.example"
if (-not (Test-Path -LiteralPath $envFile)) {
    Copy-Item -LiteralPath $envExample -Destination $envFile
    Write-Ok "建 .env(從 .env.example · 機密由 Windows 加密檔注入)"
}

$adminEmailForEnv = Get-CompanyAISecret -Name "admin-install-email"
Set-EnvValue -File $envFile -Key "ADMIN_EMAIL" -Value $adminEmailForEnv
Set-EnvValue -File $envFile -Key "ADMIN_EMAILS" -Value $adminEmailForEnv
Set-EnvValue -File $envFile -Key "ALLOW_REGISTRATION" -Value "false"
Set-EnvValue -File $envFile -Key "ALLOW_EMAIL_LOGIN" -Value "true"

& (Join-Path $InstallDir "scripts\start-windows.ps1") -ProjectDir $InstallDir -NoOpen
if ($LASTEXITCODE -ne 0) { throw "start-windows.ps1 失敗" }

Write-Step "5/6 · 檢查 / 建立第一位管理員"

$userCountText = (& docker exec company-ai-mongo mongosh company_ai --quiet --eval "db.users.countDocuments()" 2>$null | Select-Object -Last 1)
$userCount = 0
[void][int]::TryParse(($userCountText -as [string]).Trim(), [ref]$userCount)

if ($userCount -eq 0) {
    $adminEmail = Get-CompanyAISecret -Name "admin-install-email"
    $adminPassword = Get-CompanyAISecret -Name "admin-install-password"
    Write-Host "  · 建立第一位管理員帳號($adminEmail)..."
    & docker exec company-ai-librechat sh -c 'echo y | npm run create-user -- "$1" "$2" "$3" "$4"' sh $adminEmail "系統管理員" $adminEmail $adminPassword *> "$env:TEMP\company-ai-create-admin.log"
    if ($LASTEXITCODE -ne 0) {
        Get-Content "$env:TEMP\company-ai-create-admin.log" -Tail 20
        throw "建立第一位管理員失敗"
    }
    Write-Ok "第一位管理員已建立 · $adminEmail"
}
else {
    Write-Ok "使用者資料 ready (COUNT=$userCount)"
}

Write-Step "6/6 · 健康檢查"

$healthOk = $true
foreach ($url in @("http://localhost/healthz", "http://localhost/api-accounting/healthz")) {
    try {
        Invoke-WebRequest -UseBasicParsing -TimeoutSec 5 -Uri $url | Out-Null
        Write-Ok "$url · 200"
    }
    catch {
        Write-WarnLine "$url · 沒回應(可能仍在啟動)"
        $healthOk = $false
    }
}

Write-Host ""
Write-Host "═══════════════════════════════════════════════════"
Write-Host "  ✅ 企業 AI 工作台 Windows 版已就緒"
Write-Host "═══════════════════════════════════════════════════"
Write-Host ""
Write-Host "  Web UI    · http://localhost"
Write-Host "  程式碼    · $InstallDir"
Write-Host "  第一次登入 · $adminEmailForEnv / 安裝時設定的密碼"
Write-Host ""
Write-Host "  重新啟動:"
Write-Host "    powershell -ExecutionPolicy Bypass -File `"$InstallDir\scripts\start-windows.ps1`""
Write-Host "  停止:"
Write-Host "    cd `"$InstallDir\config-templates`"; docker compose down"
Write-Host "  日誌:"
Write-Host "    cd `"$InstallDir\config-templates`"; docker compose logs -f"
Write-Host ""

if ($healthOk -and -not $NoOpen) {
    Start-Process "http://localhost/" | Out-Null
}
