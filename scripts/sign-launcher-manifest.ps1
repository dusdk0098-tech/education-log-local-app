param([switch]$Verify)

$ErrorActionPreference = "Stop"
$keyName = "PEDIT-EDU-PEDIT-20260721-017-ES256"
$kid = "pedit-edu-pedit-20260721-017-es256"
$authenticodeThumbprint = "59CF023FA686F6B1FB7CFD35DD5BAAD53088181D"
$releaseDirectory = Join-Path $PSScriptRoot "..\release\launcher"
$manifestPath = Join-Path $releaseDirectory "app-manifest.json"

function ConvertTo-Base64Url([byte[]]$Value) {
  [Convert]::ToBase64String($Value).TrimEnd("=").Replace("+", "-").Replace("/", "_")
}

if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) {
  throw "RELEASE_MANIFEST_MISSING"
}

$manifest = [IO.File]::ReadAllText($manifestPath, [Text.Encoding]::UTF8) | ConvertFrom-Json
$archiveName = "pedit-edu-$($manifest.version)-windows-x64.zip"
$archivePath = Join-Path $releaseDirectory $archiveName
if (-not (Test-Path -LiteralPath $archivePath -PathType Leaf)) {
  throw "RELEASE_ARCHIVE_MISSING"
}

foreach ($relativePath in @("PeditEdu.exe", "resources\backend\PeditEduBackend.exe")) {
  $signature = Get-AuthenticodeSignature -LiteralPath (Join-Path $PSScriptRoot "..\release\win-unpacked\$relativePath")
  if ($signature.SignerCertificate.Thumbprint -ne $authenticodeThumbprint -or
      $signature.Status -notin @("Valid", "UnknownError")) {
    throw "RELEASE_AUTHENTICODE_MISMATCH:$relativePath"
  }
}

$key = [Security.Cryptography.CngKey]::Open(
  $keyName,
  [Security.Cryptography.CngProvider]::MicrosoftSoftwareKeyStorageProvider
)
try {
  if ($key.Algorithm -ne [Security.Cryptography.CngAlgorithm]::ECDsaP256 -or
      $key.ExportPolicy -ne [Security.Cryptography.CngExportPolicies]::None -or
      -not $key.KeyUsage.HasFlag([Security.Cryptography.CngKeyUsages]::Signing)) {
    throw "RELEASE_MANIFEST_KEY_INVALID"
  }
  $header = ConvertTo-Base64Url([Text.Encoding]::UTF8.GetBytes("{`"alg`":`"ES256`",`"kid`":`"$kid`",`"typ`":`"pedit-app-manifest+jws`"}"))
  $payload = ConvertTo-Base64Url([IO.File]::ReadAllBytes($manifestPath))
  $input = [Text.Encoding]::ASCII.GetBytes("$header.$payload")
  $signer = [Security.Cryptography.ECDsaCng]::new($key)
  try { $signature = $signer.SignData($input, [Security.Cryptography.HashAlgorithmName]::SHA256) }
  finally { $signer.Dispose() }
  if ($signature.Length -ne 64) { throw "RELEASE_MANIFEST_SIGNATURE_INVALID" }
  $jwsPath = Join-Path $releaseDirectory "app-manifest.jws"
  [IO.File]::WriteAllText($jwsPath, "$header.$payload.$(ConvertTo-Base64Url($signature))", [Text.UTF8Encoding]::new($false))

  $checksumEntries = @($archiveName, "app-manifest.json", "app-manifest.jws") | Sort-Object
  $checksumLines = $checksumEntries | ForEach-Object {
    "$((Get-FileHash -LiteralPath (Join-Path $releaseDirectory $_) -Algorithm SHA256).Hash.ToLowerInvariant())  $_"
  }
  [IO.File]::WriteAllLines((Join-Path $releaseDirectory "SHA256SUMS.txt"), @($checksumLines), [Text.UTF8Encoding]::new($false))

  if ($Verify) {
    $verifier = [Security.Cryptography.ECDsaCng]::new($key)
    try {
      if (-not $verifier.VerifyData($input, $signature, [Security.Cryptography.HashAlgorithmName]::SHA256)) {
        throw "RELEASE_MANIFEST_VERIFICATION_FAILED"
      }
    } finally { $verifier.Dispose() }
    $assets = @(Get-ChildItem -LiteralPath $releaseDirectory -File | Select-Object -ExpandProperty Name | Sort-Object)
    $expected = @($archiveName, "app-manifest.json", "app-manifest.jws", "SHA256SUMS.txt") | Sort-Object
    if (Compare-Object $assets $expected) { throw "RELEASE_ASSET_SET_INVALID" }
  }
  Write-Output "release-four-assets-verified"
} finally { $key.Dispose() }
