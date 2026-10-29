$ErrorActionPreference = "Stop"

$extensionRoot = $PSScriptRoot
$repositoryRoot = Split-Path -Parent $extensionRoot
$outputDirectory = Join-Path $repositoryRoot "release"
$outputPath = Join-Path $outputDirectory "recruitmentguard-chrome-extension-v1.1.0.zip"
$publicDownloadDirectory = Join-Path $extensionRoot "downloads"
$publicDownloadPath = Join-Path $publicDownloadDirectory "recruitmentguard-chrome-extension-v1.1.0.zip"

$manifestPath = Join-Path $extensionRoot "manifest.json"
$manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
$requiredFiles = @(
    "manifest.json",
    "api.js",
    "popup.html",
    "popup.js",
    "popup.css",
    "icons/icon16.png",
    "icons/icon48.png",
    "icons/icon128.png"
)

foreach ($file in $requiredFiles) {
    if (-not (Test-Path -LiteralPath (Join-Path $extensionRoot $file) -PathType Leaf)) {
        throw "Required extension file is missing: $file"
    }
}

$html = Get-Content -LiteralPath (Join-Path $extensionRoot "popup.html") -Raw
foreach ($reference in [regex]::Matches($html, '(?:src|href)="([^"]+)"')) {
    $file = $reference.Groups[1].Value
    if ($file -match '^(https?:|data:|#)') {
        continue
    }
    if (-not (Test-Path -LiteralPath (Join-Path $extensionRoot $file) -PathType Leaf)) {
        throw "Popup references a missing file: $file"
    }
}

foreach ($icon in $manifest.icons.PSObject.Properties) {
    if (-not (Test-Path -LiteralPath (Join-Path $extensionRoot $icon.Value) -PathType Leaf)) {
        throw "Manifest references a missing icon: $($icon.Value)"
    }
}

if ($manifest.manifest_version -ne 3) {
    throw "Chrome Web Store package must use Manifest V3."
}

if (
    $manifest.host_permissions.Count -ne 1 -or
    $manifest.host_permissions[0] -ne "https://recruitment-scam-detection.onrender.com/*"
) {
    throw "The release must grant host access only to the production API."
}

if ($manifest.optional_host_permissions) {
    throw "Optional host permissions are not allowed in the production package."
}

New-Item -ItemType Directory -Force -Path $outputDirectory | Out-Null
if (Test-Path -LiteralPath $outputPath) {
    Remove-Item -LiteralPath $outputPath -Force
}

Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem
$archive = [System.IO.Compression.ZipFile]::Open(
    $outputPath,
    [System.IO.Compression.ZipArchiveMode]::Create
)
try {
    foreach ($file in $requiredFiles) {
        $source = Join-Path $extensionRoot $file
        $entryName = $file.Replace("\", "/")
        [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile(
            $archive,
            $source,
            $entryName,
            [System.IO.Compression.CompressionLevel]::Optimal
        ) | Out-Null
    }
}
finally {
    $archive.Dispose()
}

New-Item -ItemType Directory -Force -Path $publicDownloadDirectory | Out-Null
Copy-Item -LiteralPath $outputPath -Destination $publicDownloadPath -Force

Write-Output "Validated Manifest V3 files and created: $outputPath"
Write-Output "Updated public GitHub download: $publicDownloadPath"
