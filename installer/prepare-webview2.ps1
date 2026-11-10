$ErrorActionPreference = 'Stop'
$target = Join-Path $PSScriptRoot 'MicrosoftEdgeWebview2Setup.exe'
Invoke-WebRequest -Uri 'https://go.microsoft.com/fwlink/p/?LinkId=2124703' -OutFile $target
$signature = Get-AuthenticodeSignature -LiteralPath $target
if ($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Subject -notmatch 'O=Microsoft Corporation') {
    throw 'WebView2 bootstrapper signature validation failed. Do not distribute this file.'
}
Get-FileHash -LiteralPath $target -Algorithm SHA256
