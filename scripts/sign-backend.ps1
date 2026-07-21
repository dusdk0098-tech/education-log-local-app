$ErrorActionPreference = "Stop"

$thumbprint = "59CF023FA686F6B1FB7CFD35DD5BAAD53088181D"
$target = Join-Path $PSScriptRoot "..\dist-backend\PeditEduBackend.exe"
if (-not (Test-Path -LiteralPath $target -PathType Leaf)) {
    throw "BACKEND_EXECUTABLE_MISSING"
}

$certificate = Get-ChildItem -LiteralPath "Cert:\CurrentUser\My\$thumbprint" -ErrorAction Stop
if ($certificate.Thumbprint -ne $thumbprint -or -not $certificate.HasPrivateKey) {
    throw "BACKEND_SIGNING_CERTIFICATE_INVALID"
}

$signTool = Get-ChildItem -LiteralPath "$env:LOCALAPPDATA\electron-builder\Cache" -Filter "signtool.exe" -Recurse -ErrorAction Stop |
    Where-Object { $_.FullName -match "\\windows-10\\x64\\signtool\.exe$" } |
    Select-Object -First 1 -ExpandProperty FullName
if (-not $signTool) {
    throw "SIGNTOOL_NOT_FOUND"
}

& $signTool sign /sha1 $thumbprint /s My /fd SHA256 $target
if ($LASTEXITCODE -ne 0) {
    throw "BACKEND_SIGNING_FAILED"
}

$signature = Get-AuthenticodeSignature -LiteralPath $target
if ($signature.SignerCertificate.Thumbprint -ne $thumbprint) {
    throw "BACKEND_SIGNING_THUMBPRINT_MISMATCH"
}
if ($signature.Status -notin @("Valid", "UnknownError")) {
    throw "BACKEND_SIGNING_STATUS_INVALID:$($signature.Status)"
}

Write-Output "backend-signature-verified"
