# Windows DPAPI-backed secret helpers for Company AI installers.
# Values are encrypted for the current Windows user and stored outside git.

Set-StrictMode -Version 2.0

$script:CompanyAIProjectDir = $null
$script:CompanyAIServicePrefix = "company-ai"

function Initialize-CompanyAISecretStore {
    param(
        [Parameter(Mandatory = $true)][string]$ProjectDir,
        [string]$ServicePrefix = "company-ai"
    )

    $resolvedProject = Resolve-Path -LiteralPath $ProjectDir
    $script:CompanyAIProjectDir = $resolvedProject.Path
    $script:CompanyAIServicePrefix = $ServicePrefix
}

function Get-CompanyAISecretDir {
    if ([string]::IsNullOrWhiteSpace($script:CompanyAIProjectDir)) {
        throw "Secret store is not initialized. Call Initialize-CompanyAISecretStore first."
    }
    return (Join-Path $script:CompanyAIProjectDir "config-templates\.secrets")
}

function ConvertTo-CompanyAIPlainText {
    param([System.Security.SecureString]$SecureString)

    if ($null -eq $SecureString) {
        return ""
    }

    $ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($SecureString)
    try {
        return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)
    }
    finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)
    }
}

function Get-CompanyAISecretPath {
    param([Parameter(Mandatory = $true)][string]$Name)

    $safeName = $Name -replace '[^A-Za-z0-9_.-]', '_'
    return (Join-Path (Get-CompanyAISecretDir) "$($script:CompanyAIServicePrefix)-$safeName.txt")
}

function Set-CompanyAISecret {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$Value
    )

    $secretDir = Get-CompanyAISecretDir
    if (-not (Test-Path -LiteralPath $secretDir)) {
        New-Item -ItemType Directory -Path $secretDir -Force | Out-Null
    }

    $secureValue = ConvertTo-SecureString -String $Value -AsPlainText -Force
    $encryptedValue = ConvertFrom-SecureString -SecureString $secureValue
    Set-Content -LiteralPath (Get-CompanyAISecretPath -Name $Name) -Value $encryptedValue -Encoding ASCII
}

function Get-CompanyAISecret {
    param([Parameter(Mandatory = $true)][string]$Name)

    $path = Get-CompanyAISecretPath -Name $Name
    if (-not (Test-Path -LiteralPath $path)) {
        return ""
    }

    try {
        $encryptedValue = Get-Content -LiteralPath $path -Raw
        $secureValue = ConvertTo-SecureString -String $encryptedValue
        return (ConvertTo-CompanyAIPlainText -SecureString $secureValue)
    }
    catch {
        return ""
    }
}

function Test-CompanyAISecret {
    param([Parameter(Mandatory = $true)][string]$Name)

    return -not [string]::IsNullOrWhiteSpace((Get-CompanyAISecret -Name $Name))
}

function New-CompanyAIHexSecret {
    param([int]$Bytes = 32)

    $buffer = New-Object byte[] $Bytes
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $rng.GetBytes($buffer)
    }
    finally {
        $rng.Dispose()
    }

    return (($buffer | ForEach-Object { $_.ToString("x2") }) -join "")
}

function Ensure-CompanyAIGeneratedSecret {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [int]$Bytes = 32
    )

    if (Test-CompanyAISecret -Name $Name) {
        return
    }

    Set-CompanyAISecret -Name $Name -Value (New-CompanyAIHexSecret -Bytes $Bytes)
}
