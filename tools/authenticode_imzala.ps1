# Authenticode imzası + RFC 3161 zaman damgası (Faz 1.4). Sertifika SATIN ALINMADI; betik hazır bekler.
# Seçenekler ve karşılaştırma: docs/YANLIS_POZITIF.md.
#
# Kullanım (Windows SDK signtool gerekir):
#   tools\authenticode_imzala.ps1 -Dosya dist\Forevermore\Forevermore.exe -Parmakizi <SHA1>
#       Sertifika Windows sertifika deposunda (Certum SimplySign bulut anahtarı, USB token).
#   tools\authenticode_imzala.ps1 -Dosya <exe> -Metadata metadata.json -Dlib <yol>\Azure.CodeSigning.Dlib.dll
#       Microsoft bulut imzalama (Artifact Signing); Türkiye'den bireysel başvuruya açık değil.
#   tools\authenticode_imzala.ps1 -Dosya <exe> -Pfx sinama.pfx -PfxSifre <şifre>
#       YALNIZCA yerel deneme (kendinden imzalı sınama sertifikası); dağıtılacak pakette kullanılmaz.
#
# Sıra önemli: Authenticode .exe'nin baytlarını değiştirir; tools\imzala.py (paket özeti) bundan SONRA çalışmalı.

param(
    [Parameter(Mandatory = $true)][string[]]$Dosya,
    [string]$Parmakizi,
    [string]$Pfx,
    [string]$PfxSifre,
    [string]$Metadata,
    [string]$Dlib,
    [string]$ZamanDamgasi
)

$ErrorActionPreference = 'Stop'

function Signtool-Bul {
    $kok = Join-Path ${env:ProgramFiles(x86)} 'Windows Kits\10\bin'
    $aday = Get-ChildItem $kok -Directory -ErrorAction SilentlyContinue | Sort-Object Name -Descending |
        ForEach-Object { Join-Path $_.FullName 'x64\signtool.exe' } | Where-Object { Test-Path $_ } | Select-Object -First 1
    if (-not $aday) { throw 'signtool.exe bulunamadı: Windows SDK (Signing Tools) kurun.' }
    $aday
}

$secim = @($Parmakizi, $Pfx, $Metadata) | Where-Object { $_ }
if ($secim.Count -ne 1) { throw 'Tam olarak biri verilmeli: -Parmakizi, -Pfx veya -Metadata (+ -Dlib).' }
if ($Metadata -and -not $Dlib) { throw '-Metadata ile -Dlib (Azure.CodeSigning.Dlib.dll yolu) gerekir.' }
if (-not $ZamanDamgasi) {
    $ZamanDamgasi = if ($Metadata) { 'http://timestamp.acs.microsoft.com' } else { 'http://timestamp.digicert.com' }
}

$signtool = Signtool-Bul
$arguman = @('sign', '/fd', 'SHA256', '/tr', $ZamanDamgasi, '/td', 'SHA256', '/d', 'Forevermore')
if ($Parmakizi) { $arguman += @('/sha1', $Parmakizi) }
if ($Pfx) { $arguman += @('/f', $Pfx); if ($PfxSifre) { $arguman += @('/p', $PfxSifre) } }
if ($Metadata) { $arguman += @('/dlib', $Dlib, '/dmdf', $Metadata) }

foreach ($f in $Dosya) {
    if (-not (Test-Path $f)) { throw "Dosya yok: $f" }
    & $signtool @arguman $f
    if ($LASTEXITCODE -ne 0) { throw "signtool imzalayamadı: $f (çıkış $LASTEXITCODE)" }
    $imza = Get-AuthenticodeSignature $f
    $zaman = if ($imza.TimeStamperCertificate) { 'var' } else { 'YOK' }
    Write-Host "$f -> durum: $($imza.Status), imzalayan: $($imza.SignerCertificate.Subject), zaman damgası: $zaman"
    if (-not $imza.TimeStamperCertificate) { throw "Zaman damgası eklenmedi: $f" }
    # Sınama sertifikası güvenilir köke zincirlenmez (UnknownError beklenir); gerçek sertifikada Valid olmalı.
    if (-not $Pfx -and $imza.Status -ne 'Valid') { throw "İmza geçerli değil: $($imza.StatusMessage)" }
}
