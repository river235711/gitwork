param(
    [ValidateSet("standalone", "onefile")]
    [string]$Mode = "standalone",
    [string]$InstallDir = "/apps/cadsemi/pvflow/current",
    [string]$MaxGlibc = "2.17"
)

$ErrorActionPreference = "Stop"

$UbuntuSrc = "/home/willhuang/work/gitwork/python/cgui"
$DistDir = "$UbuntuSrc/dist"
$Version = "26.11.001"
$SysTxt = Join-Path $PSScriptRoot "data\system.txt"
if (Test-Path $SysTxt) {
    foreach ($line in Get-Content $SysTxt) {
        if ($line -match '^\s*(\d+(?:\.\d+)+)\s+\d{4}/\d{2}/\d{2}') {
            $Version = $Matches[1]
            break
        }
    }
}
$OutTarName = "pvflow_${Version}_linux_x64.tar.gz"

$StageTarWin = Join-Path $env:TEMP ("pvflow_src_stage_" + [guid]::NewGuid().ToString("N") + ".tar")
$OutTarWin = Join-Path $env:TEMP ("pvflow_out_stage_" + [guid]::NewGuid().ToString("N") + ".tar.gz")

function Convert-ToWslPath([string]$WinPath) {
    $drive = $WinPath.Substring(0, 1).ToLower()
    $rest = $WinPath.Substring(2).Replace("\", "/")
    return "/mnt/$drive$rest"
}

$StageTarWsl = Convert-ToWslPath $StageTarWin
$OutTarWsl = Convert-ToWslPath $OutTarWin

try {
    Write-Host "[1/4] Staging clean PVFlow source (excluding private keys, tests, build artifacts)..."
    & wsl -d Ubuntu -- tar -C $UbuntuSrc `
        --exclude=.build_venv `
        --exclude=build_nuitka `
        --exclude=dist `
        --exclude=lic_issuer `
        --exclude=tests `
        --exclude=__pycache__ `
        --exclude="*.pyc" `
        --exclude="*.pyo" `
        --exclude="*.pem" `
        --exclude="*.lic" `
        -cf $StageTarWsl .
    if ($LASTEXITCODE -ne 0) { throw "Failed to stage source tarball from Ubuntu." }

    Write-Host "[2/4] Building PVFlow $Version inside WSL CentOS7Build (glibc <= $MaxGlibc, mode=$Mode)..."
    $BuildCmd = @(
        "set -euo pipefail",
        "rm -rf /root/pvflow_build",
        "mkdir -p /root/pvflow_build",
        "tar -xf '$StageTarWsl' -C /root/pvflow_build",
        "export PATH=/opt/cgui-py312/bin:/opt/rh/devtoolset-10/root/usr/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
        "export SSL_CERT_FILE=/opt/_internal/certs.pem",
        "/opt/cgui-py312/bin/python3 /root/pvflow_build/cgui_build_nuitka.py --mode $Mode --version '$Version' --out '/root/pvflow_build/dist/$Version' --install-dir '$InstallDir' --max-glibc '$MaxGlibc'",
        "tar -C /root/pvflow_build/dist -czf '$OutTarWsl' '$Version'",
        "rm -rf /root/pvflow_build"
    ) -join "; "
    & wsl -d CentOS7Build -- bash -c $BuildCmd
    if ($LASTEXITCODE -ne 0) { throw "Nuitka build failed inside CentOS7Build." }

    Write-Host "[3/4] Landing RHEL 7+ deliverable into Ubuntu $DistDir..."
    $LandCmd = @(
        "set -euo pipefail",
        "mkdir -p '$DistDir'",
        "rm -rf '$DistDir/$Version'",
        "cp '$OutTarWsl' '$DistDir/$OutTarName'",
        "tar -C '$DistDir' -xzf '$DistDir/$OutTarName'"
    ) -join "; "
    & wsl -d Ubuntu -- bash -c $LandCmd
    if ($LASTEXITCODE -ne 0) { throw "Failed to land RHEL 7 build into Ubuntu dist/." }

    Write-Host "[4/4] Done!"
    Write-Host "  Release directory : $DistDir/$Version/"
    Write-Host "  Release tarball   : $DistDir/$OutTarName"
    Write-Host "  Extract on Linux  : tar -xzf $OutTarName -C /apps/cadsemi/pvflow/"
}
finally {
    Remove-Item -Force -ErrorAction SilentlyContinue $StageTarWin, $OutTarWin
}
