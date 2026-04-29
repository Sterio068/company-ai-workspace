#Requires -Version 5.1
<#
企業 AI 工作台 · Windows 啟動腳本

用法:
  powershell -ExecutionPolicy Bypass -File .\scripts\start-windows.ps1
  powershell -ExecutionPolicy Bypass -File .\scripts\start-windows.ps1 -NoOpen
#>

[CmdletBinding()]
param(
    [string]$ProjectDir,
    [switch]$NoOpen
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = "Stop"

function Write-Ok { param([string]$Text) Write-Host "  ✓ $Text" -ForegroundColor Green }
function Write-WarnLine { param([string]$Text) Write-Host "  ⚠ $Text" -ForegroundColor Yellow }
function Write-Step { param([string]$Text) Write-Host ""; Write-Host $Text -ForegroundColor Cyan }

if ([string]::IsNullOrWhiteSpace($ProjectDir)) {
    $ProjectDir = Split-Path -Parent $PSScriptRoot
}
$ProjectDir = (Resolve-Path -LiteralPath $ProjectDir).Path

. (Join-Path $PSScriptRoot "windows-secrets.ps1")
Initialize-CompanyAISecretStore -ProjectDir $ProjectDir -ServicePrefix "company-ai"

Write-Host "============================================"
Write-Host "  企業 AI 工作台 · Windows 啟動中"
Write-Host "============================================"

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "找不到 docker。請先安裝 Docker Desktop for Windows 後重跑。下載: https://www.docker.com/products/docker-desktop/"
}

& docker info *> $null
if ($LASTEXITCODE -ne 0) {
    Write-WarnLine "Docker daemon 尚未啟動,嘗試開啟 Docker Desktop..."
    $dockerDesktopPaths = @(
        "$env:ProgramFiles\Docker\Docker\Docker Desktop.exe",
        "${env:ProgramFiles(x86)}\Docker\Docker\Docker Desktop.exe"
    )
    $dockerDesktop = $dockerDesktopPaths | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
    if ($dockerDesktop) {
        Start-Process -FilePath $dockerDesktop | Out-Null
    }

    $ready = $false
    for ($i = 1; $i -le 90; $i++) {
        Start-Sleep -Seconds 2
        & docker info *> $null
        if ($LASTEXITCODE -eq 0) {
            $ready = $true
            break
        }
        Write-Host "." -NoNewline
    }
    Write-Host ""
    if (-not $ready) {
        throw "Docker Desktop 180 秒內未就緒。若這是首次安裝,請完成 Docker Desktop 畫面上的 WSL2/授權步驟後重跑。"
    }
}

$envFile = Join-Path $ProjectDir "config-templates\.env"
if (-not (Test-Path -LiteralPath $envFile)) {
    throw "找不到 $envFile。請先執行 installer\install.ps1。"
}

Write-Step "[1/3] 讀取 Windows 加密機密"

$openAIKey = Get-CompanyAISecret -Name "openai-key"
$anthropicKey = Get-CompanyAISecret -Name "anthropic-key"
if ([string]::IsNullOrWhiteSpace($openAIKey) -and [string]::IsNullOrWhiteSpace($anthropicKey)) {
    throw "至少需要 OpenAI 或 Claude API Key。請重跑 installer\install.ps1 設定。"
}
if ([string]::IsNullOrWhiteSpace($openAIKey)) {
    Write-WarnLine "OpenAI Key 未設定 · OpenAI 引擎不可用"
}
if ([string]::IsNullOrWhiteSpace($anthropicKey)) {
    Write-WarnLine "Claude Key 未設定 · Claude 備援不可用"
}

Ensure-CompanyAIGeneratedSecret -Name "jwt-secret" -Bytes 32
Ensure-CompanyAIGeneratedSecret -Name "jwt-refresh-secret" -Bytes 32
Ensure-CompanyAIGeneratedSecret -Name "creds-key" -Bytes 32
Ensure-CompanyAIGeneratedSecret -Name "creds-iv" -Bytes 16
Ensure-CompanyAIGeneratedSecret -Name "meili-master-key" -Bytes 32
Ensure-CompanyAIGeneratedSecret -Name "internal-token" -Bytes 32
Ensure-CompanyAIGeneratedSecret -Name "action-bridge-token" -Bytes 32

$env:OPENAI_API_KEY = $openAIKey
$env:ANTHROPIC_API_KEY = $anthropicKey
$env:EMAIL_PASSWORD = Get-CompanyAISecret -Name "email-password"
$env:NOTEBOOKLM_ACCESS_TOKEN = Get-CompanyAISecret -Name "notebooklm-access-token"
$env:JWT_SECRET = Get-CompanyAISecret -Name "jwt-secret"
$env:JWT_REFRESH_SECRET = Get-CompanyAISecret -Name "jwt-refresh-secret"
$env:CREDS_KEY = Get-CompanyAISecret -Name "creds-key"
$env:CREDS_IV = Get-CompanyAISecret -Name "creds-iv"
$env:MEILI_MASTER_KEY = Get-CompanyAISecret -Name "meili-master-key"
$env:ECC_INTERNAL_TOKEN = Get-CompanyAISecret -Name "internal-token"
$env:ACTION_BRIDGE_TOKEN = Get-CompanyAISecret -Name "action-bridge-token"

Write-Ok "機密已注入目前 PowerShell process"

$launcherDir = Join-Path $ProjectDir "frontend\launcher"
$indexHtml = Join-Path $launcherDir "index.html"
if (Test-Path -LiteralPath $indexHtml) {
    $indexContent = Get-Content -LiteralPath $indexHtml -Raw
    $match = [regex]::Match($indexContent, "dist/app\.[A-Z0-9]+\.js")
    if ($match.Success) {
        $bundlePath = Join-Path $launcherDir ($match.Value -replace "/", [IO.Path]::DirectorySeparatorChar)
        if (-not (Test-Path -LiteralPath $bundlePath)) {
            Write-WarnLine "launcher dist 缺少 bundle,嘗試 npm build..."
            if (Get-Command npm -ErrorAction SilentlyContinue) {
                Push-Location $launcherDir
                try {
                    if (-not (Test-Path -LiteralPath "node_modules")) {
                        & npm install --silent
                    }
                    & npm run build
                }
                finally {
                    Pop-Location
                }
            }
            else {
                Write-WarnLine "找不到 npm,略過 build。若前端 404,請安裝 Node.js 後重跑。"
            }
        }
    }
}

$networkFile = Join-Path $ProjectDir "config-templates\.host-network.json"
try {
    $lanIps = @(Get-NetIPAddress -AddressFamily IPv4 -ErrorAction Stop |
        Where-Object { $_.IPAddress -notlike "127.*" -and $_.IPAddress -notlike "169.254.*" } |
        Select-Object -ExpandProperty IPAddress)
}
catch {
    $lanIps = @()
}
$hostName = if ($env:COMPUTERNAME) { "$($env:COMPUTERNAME.ToLower()).local" } else { "windows.local" }
$networkPayload = [ordered]@{
    lan_ips = $lanIps
    hostname = $hostName
    tunnel_hostnames = @()
    detected_at = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
}
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($networkFile, ($networkPayload | ConvertTo-Json -Depth 4), $utf8NoBom)
Write-Ok "網路資訊已寫入 .host-network.json"

Write-Step "[2/3] 啟動 Docker Compose"

$composeDir = Join-Path $ProjectDir "config-templates"
Push-Location $composeDir
try {
    if ([string]::IsNullOrWhiteSpace($env:COMPOSE_FILE)) {
        $env:COMPOSE_FILE = "docker-compose.yml"
        Write-Host "  🔒 PROD 模式 · 不 merge override"
    }

    $shouldBuildAccounting = $false
    & docker image inspect config-templates-accounting *> $null
    if ($LASTEXITCODE -ne 0) {
        $shouldBuildAccounting = $true
    }
    else {
        $createdRaw = (& docker image inspect config-templates-accounting --format "{{.Created}}" 2>$null | Select-Object -First 1)
        $imageCreated = [DateTimeOffset]::Parse($createdRaw).UtcDateTime
        $accountingDir = Join-Path $ProjectDir "backend\accounting"
        $newestSource = Get-ChildItem -LiteralPath $accountingDir -Recurse -File |
            Where-Object { $_.FullName -notmatch "\\(__pycache__|\.pytest_cache)\\" } |
            Sort-Object LastWriteTimeUtc -Descending |
            Select-Object -First 1
        if ($newestSource -and $newestSource.LastWriteTimeUtc -gt $imageCreated) {
            $shouldBuildAccounting = $true
        }
    }

    if ($shouldBuildAccounting) {
        Write-Host "  🔨 accounting image 需要 rebuild..."
        & docker compose build accounting
        if ($LASTEXITCODE -ne 0) { throw "docker compose build accounting 失敗" }
    }

    & docker compose up -d
    if ($LASTEXITCODE -ne 0) { throw "docker compose up -d 失敗" }
}
finally {
    Pop-Location
}

Write-Step "[3/3] 等 nginx + LibreChat 就緒"
$ready = $false
for ($i = 1; $i -le 90; $i++) {
    try {
        Invoke-WebRequest -UseBasicParsing -TimeoutSec 5 -Uri "http://localhost/healthz" | Out-Null
        Invoke-WebRequest -UseBasicParsing -TimeoutSec 5 -Uri "http://localhost/api/config" | Out-Null
        Write-Ok "全部就緒(${i}s)"
        $ready = $true
        break
    }
    catch {
        Start-Sleep -Seconds 1
    }
}
if (-not $ready) {
    Write-WarnLine "90 秒內未完全就緒。可查看: cd $composeDir; docker compose logs -f"
}

Write-Host ""
Write-Host "============================================"
Write-Host "  ✅ 企業 AI 工作台已啟動"
Write-Host "============================================"
Write-Host ""
Write-Host "  本機入口:  http://localhost/"
Write-Host "  API 文件:  http://localhost/api-accounting/docs"
Write-Host "  Uptime:    http://localhost:3001"
Write-Host ""
Write-Host "  停止:"
Write-Host "    cd `"$composeDir`"; docker compose down"
Write-Host "  日誌:"
Write-Host "    cd `"$composeDir`"; docker compose logs -f"
Write-Host ""

if (-not $NoOpen) {
    Start-Process "http://localhost/" | Out-Null
}
