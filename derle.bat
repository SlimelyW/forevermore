@echo off
rem Çift tıkla: dist\Forevermore\ klasörünü ve paylaşım için dist\Forevermore.zip dosyasını üretir.
rem Yalnızca kişisel deneme için tek dosya: derle.bat -TekDosya
chcp 65001 >nul
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\derle.ps1" %*
echo.
pause
