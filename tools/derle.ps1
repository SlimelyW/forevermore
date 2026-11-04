# Forevermore derleme betiği.
#
# Kullanım (proje klasöründe derle.bat'a çift tıkla veya):
#   powershell -ExecutionPolicy Bypass -File tools\derle.ps1            -> klasör: dist\Forevermore\ + dist\Forevermore.zip
#   powershell -ExecutionPolicy Bypass -File tools\derle.ps1 -TekDosya  -> tek dosya: dist\Forevermore.exe (yalnızca kişisel deneme)
#
# Neden klasör? Arayüz kütüphanesi Qt (PySide6) LGPLv3 lisanslıdır; Qt kitaplıklarının
# ayrı dosyalar olarak dağıtılması lisans koşullarını karşılamanın en açık yoludur.
# Arkadaşına dist\Forevermore.zip dosyasını gönder; zip'i açıp içindeki Forevermore.exe'yi çalıştırsın.
#
# Ne yapar: ayrı bir derleme ortamı (.venv-derleme) kurar, veriyi yeniden üretir,
# testleri çalıştırır (biri başarısızsa durur), derler ve programın dosyalarını
# bulabildiğini pencere açmadan kontrol eder. Bilgisayarında hiçbir Windows ayarını değiştirmez.

param([switch]$TekDosya)

$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
Set-Location $root

function Adim($metin) { Write-Host "`n==> $metin" -ForegroundColor Cyan }

# Python'u çalıştırır. Windows PowerShell 5.1'de $ErrorActionPreference='Stop' iken bir programın stderr'e
# yazdığı uyarı (pip, PyInstaller, unittest) hata sayılıp betiği durduruyordu; burada düz metin olarak
# gösterilir, başarı $LASTEXITCODE ile denetlenir.
function Py {
    $old = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    $env:PYTHONUTF8 = '1'  # çıktı boruya gidince Python cp1252'ye düşüp Türkçe karakterde çöküyordu
    [Console]::OutputEncoding = [Text.Encoding]::UTF8
    try { & $py @args 2>&1 | ForEach-Object {
        if ($_ -is [System.Management.Automation.ErrorRecord]) { "$($_.TargetObject)" } else { "$_" } } } finally { $ErrorActionPreference = $old }
}

Adim "Derleme ortamı hazırlanıyor (.venv-derleme)"
if (-not (Test-Path '.venv-derleme\Scripts\python.exe')) { py -3.12 -m venv .venv-derleme }
$py = Join-Path $root '.venv-derleme\Scripts\python.exe'
Py -m pip install --quiet --disable-pip-version-check -r requirements-derleme.txt
if ($LASTEXITCODE -ne 0) { throw 'Paketler kurulamadı (internet bağlantısını kontrol et).' }

Adim "Ayar veritabanı yeniden üretiliyor"
Py tools\convert_tweaks.py
if ($LASTEXITCODE -ne 0) { throw 'Veri dönüştürmede hata var; tools\donusum_raporu.md dosyasına bak.' }

Adim "Testler çalışıyor"
$env:QT_QPA_PLATFORM = 'offscreen'  # arayüz testleri pencere açmaz
Py -m unittest discover -s tests -t .
$testCode = $LASTEXITCODE
Remove-Item Env:QT_QPA_PLATFORM -ErrorAction SilentlyContinue
if ($testCode -ne 0) { throw 'Testler başarısız; program derlenmedi.' }

Adim "Derleniyor ($(if ($TekDosya) {'tek dosya'} else {'klasör'}))"
if ($TekDosya) { $env:PCOPT_ONEFILE = '1' } else { Remove-Item Env:PCOPT_ONEFILE -ErrorAction SilentlyContinue }
# Tekrarlanabilir derleme (PyInstaller belgesi "advanced-topics"): sabit karma tohumu ve son commit'in zamanı.
# Aynı commit + aynı klasör yolu + aynı paket sürümleri aynı .exe'yi verir; zip zaman damgaları yine değişir.
$env:PYTHONHASHSEED = '0'
$commitZamani = try { git log -1 --format=%ct 2>$null } catch { $null }  # git yoksa zaman sabitlenmez
if ($commitZamani) { $env:SOURCE_DATE_EPOCH = $commitZamani }
Py -m PyInstaller build\forevermore.spec --noconfirm --clean --workpath .derleme --distpath dist
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller hata verdi.' }

$exe = if ($TekDosya) { 'dist\Forevermore.exe' } else { 'dist\Forevermore\Forevermore.exe' }
# Authenticode (docs/YANLIS_POZITIF.md): sertifika tanımlıysa .exe imzalanır. Paket özetinden (imzala.py) ÖNCE olmalı.
if ($env:FOREVERMORE_IMZA_PARMAKIZI -or $env:FOREVERMORE_IMZA_METADATA) {
    Adim "Authenticode imzası + zaman damgası"
    $imzaArg = @{ Dosya = $exe }
    if ($env:FOREVERMORE_IMZA_PARMAKIZI) { $imzaArg.Parmakizi = $env:FOREVERMORE_IMZA_PARMAKIZI }
    else { $imzaArg.Metadata = $env:FOREVERMORE_IMZA_METADATA; $imzaArg.Dlib = $env:FOREVERMORE_IMZA_DLIB }
    & (Join-Path $PSScriptRoot 'authenticode_imzala.ps1') @imzaArg
} else {
    Write-Host 'Uyarı: Authenticode sertifikası tanımlı değil (FOREVERMORE_IMZA_PARMAKIZI); .exe imzasız, SmartScreen uyarır.' -ForegroundColor Yellow
}

if ($TekDosya) {
    $paket = $exe
} else {
    foreach ($f in 'LICENSE', 'THIRD-PARTY-NOTICES.txt') { Copy-Item $f 'dist\Forevermore\' -Force }
    Copy-Item 'docs\OKUBENI.txt' 'dist\Forevermore\' -Force
    # PresentMon (MIT, Intel): tools klasörüne konduysa programın yanına kopyalanır.
    $pm = Get-ChildItem 'tools\PresentMon*.exe' -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($pm) {
        Copy-Item $pm.FullName 'dist\Forevermore\' -Force
        Write-Host "PresentMon eklendi: $($pm.Name)"
    } else {
        Write-Host 'Uyarı: tools\PresentMon*.exe yok; oyun FPS ölçümü bu pakette çalışmaz.'
    }

    # İmza en son: klasöre dosya eklendikten sonra yapılmalı. Özel anahtar yalnızca yapımcının
    # bilgisayarında (%USERPROFILE%\.forevermore-imza); yoksa paket imzasız kalır.
    Adim "Paket imzalanıyor"
    Py tools\imzala.py imzala dist\Forevermore
    if ($LASTEXITCODE -eq 1) { throw 'İmza denetimi başarısız.' }
    if ($LASTEXITCODE -eq 2) { Write-Host 'Uyarı: paket İMZASIZ (dağıtıma uygun değil).' -ForegroundColor Yellow }
}

Adim "Paket kontrolü (pencere açılmaz, ayar değiştirmez)"
$p = Start-Process -FilePath $exe -ArgumentList '--kontrol' -Wait -PassThru
Get-Content (Join-Path $env:LOCALAPPDATA 'Forevermore\logs\kontrol.txt')
if ($p.ExitCode -ne 0) { throw 'Paket kontrolü başarısız.' }

if (-not $TekDosya) {
    Adim "Paylaşım için zip hazırlanıyor"
    $paket = 'dist\Forevermore.zip'
    if (Test-Path $paket) { Remove-Item $paket }
    Compress-Archive -Path 'dist\Forevermore' -DestinationPath $paket
}

Adim "Bitti"
$hash = (Get-FileHash $paket -Algorithm SHA256).Hash
$size = [math]::Round((Get-Item $paket).Length / 1MB, 1)
Write-Host "Dosya : $paket ($size MB)"
Write-Host "SHA256: $hash"
Set-Content -Path "$paket.sha256.txt" -Value "$hash  $(Split-Path $paket -Leaf)" -Encoding ascii
Write-Host "Arkadaşına gönderirken bu SHA256 değerini de paylaş; dosyanın yolda değişmediğini doğrulayabilir."
