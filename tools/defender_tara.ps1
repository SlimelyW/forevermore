# Derlenmiş paketi Microsoft Defender ile tarar ve tespit adını yazar (Faz 1.4). Ayar DEĞİŞTİRMEZ.
# Nerede: güncel Defender'lı TEMİZ bir sanal makinede (bulut koruması ve örnek gönderimi açık, varsayılan ayarlar).
# Geliştirici bilgisayarında çalıştırmayın: tespit olursa Defender dosyayı karantinaya alabilir.
#
# Kullanım (yönetici PowerShell):
#   powershell -NoProfile -File tools\defender_tara.ps1 -Yol C:\deneme\Forevermore.zip
#   powershell -NoProfile -File tools\defender_tara.ps1 -Yol C:\deneme\Forevermore      (açılmış klasör)
# Çıktı: ekrana özet + <Yol>.defender.json (sürüm, imza sürümü, SHA256, tespitler). Sonucu docs/YANLIS_POZITIF.md tablosuna yazın.

param(
    [Parameter(Mandatory = $true)][string]$Yol,
    [switch]$ImzaGuncelleme   # önce Defender tanımlarını günceller (Update-MpSignature)
)

$ErrorActionPreference = 'Stop'
$Yol = (Resolve-Path $Yol).Path
if ($ImzaGuncelleme) { Update-MpSignature }

$durum = Get-MpComputerStatus
$baslangic = Get-Date
Start-MpScan -ScanType CustomScan -ScanPath $Yol
Start-Sleep -Seconds 5   # tespit kaydı tarama bitince birkaç saniyede düşer

$tehditler = @{}
Get-MpThreat -ErrorAction SilentlyContinue | ForEach-Object { $tehditler[$_.ThreatID] = $_.ThreatName }
$tespitler = @(Get-MpThreatDetection -ErrorAction SilentlyContinue |
    Where-Object { $_.InitialDetectionTime -ge $baslangic.AddMinutes(-1) -and ($_.Resources -join ' ') -like "*$(Split-Path $Yol -Leaf)*" } |
    ForEach-Object {
        [pscustomobject]@{
            ad       = $tehditler[$_.ThreatID]
            kimlik   = $_.ThreatID
            dosyalar = @($_.Resources)
            eylem    = [string]$_.ActionSuccess
            zaman    = $_.InitialDetectionTime.ToString('s')
        }
    })

$ozet = if (Test-Path $Yol -PathType Leaf) { (Get-FileHash $Yol -Algorithm SHA256).Hash } else {
    $exe = Join-Path $Yol 'Forevermore.exe'
    if (Test-Path $exe) { (Get-FileHash $exe -Algorithm SHA256).Hash } else { '' }
}
$sonuc = [pscustomobject]@{
    tarih            = $baslangic.ToString('s')
    yol              = $Yol
    sha256           = $ozet
    defender_motoru  = $durum.AMEngineVersion
    imza_surumu      = $durum.AntivirusSignatureVersion
    bulut_korumasi   = (Get-MpPreference).MAPSReporting
    tespit_sayisi    = $tespitler.Count
    tespitler        = $tespitler
}
$cikti = "$Yol.defender.json"
$sonuc | ConvertTo-Json -Depth 5 | Set-Content -Path $cikti -Encoding UTF8
if ($tespitler.Count) {
    Write-Host "TESPİT: $(($tespitler | ForEach-Object { $_.ad }) -join ', ')" -ForegroundColor Red
} else {
    Write-Host 'Tespit yok.' -ForegroundColor Green
}
Write-Host "SHA256: $ozet  | Defender imza sürümü: $($durum.AntivirusSignatureVersion)  | Kayıt: $cikti"
