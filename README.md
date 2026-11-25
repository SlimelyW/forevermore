# Forevermore

A free, open-source (MIT) Windows 10/11 settings app for gamers. It scans your PC, explains what each setting does with
its pros and cons and an evidence label (real / partial / situational / debated / placebo / harmful), and backs up every
change so it can be undone with one click. No Pro tier, no account, no ads, no telemetry.

The app is English by default. Other languages (Turkish, Spanish, German, Russian, Simplified Chinese) can be picked in
Settings; they are machine translations and have not been reviewed by native speakers.

## What it does

- **Scan and PC details:** reads hardware, drivers, power plan, display, mouse/keyboard and Windows state (read-only).
- **167 settings, each with an evidence label:** real, partial, situational, debated, placebo or harmful, with source and
  measurement notes. Risky settings ask twice.
- **Every change is reversible:** a backup (and, when needed, a system restore point) is made first; undo from the Changes page.
- **GPU settings:** NVIDIA (NVAPI) and AMD (ADLX) driver settings, scaling, G-SYNC / FreeSync.
- **Games:** per-game process priority and optional "while playing" options (off by default). They apply only when you press
  Prepare / Launch and are undone when the game closes or you press Undo. No process tweaks for games with anti-cheat.
- **Profiles, one-click Boost, app uninstaller, display layout, Before / After measurement** (FPS and frame time via PresentMon).

All features are available to everyone; nothing is locked.

## Important: it changes system settings

Forevermore **can change the registry, services, boot options and GPU driver settings**.

- It tries to create a **system restore point** before the first change and **backs up** every value it writes; you can undo
  from the Changes page.
- It asks for **administrator rights** only to apply changes. Without them it opens read-only (scan and guides work).
  `--onizleme` lets you try everything without changing anything.
- Some settings reduce security (for example Spectre/Meltdown mitigations) or need a restart; the app says so before you
  confirm. Read what you are approving. The software is provided **"as is", without warranty** (see [LICENSE](LICENSE)).
- It does not fully disable Windows Defender, does not interfere with anti-cheat, and has no "memory cleaner" style
  placebo tools.

## Install

1. Download `Forevermore.zip` from [Releases](https://github.com/SlimelyW/forevermore/releases/latest).
2. Extract it to a folder (keep the folder intact; `_internal` is part of the program) and run **Forevermore.exe**.
3. To uninstall, first use Settings > "Prepare for removal" to undo changes, then delete the folder.

**Check your download (two steps):**
1. In PowerShell, in the folder with the zip: `Get-FileHash .\Forevermore.zip -Algorithm SHA256`
2. Compare the result with the SHA-256 on the Releases page. If it differs, do not run it; download again.

**Windows or your antivirus may show a warning.** This is expected: the program is not code-signed yet and is new, so
SmartScreen has no reputation for it. Programs packaged with Python + PyInstaller can also trigger false positives in
some antivirus products. The source is open, so you can read it and build the package yourself. Do not turn your
antivirus off.

## Run from source and build

Requirements: Windows 10/11, Python 3.12.

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt

.venv\Scripts\python -m app                 # run (asks for admin rights to write settings)
.venv\Scripts\python -m app --onizleme      # try without changing any setting (preview)
.venv\Scripts\python -m app --kontrol       # package self-check without opening a window
```

Tests (no window, no real system settings written):

```powershell
$env:QT_QPA_PLATFORM = "offscreen"
.venv\Scripts\python -m unittest discover -s tests -t .
```

Build a package (`dist\Forevermore\` and `dist\Forevermore.zip`):

```powershell
.\derle.bat
```

`derle.bat` sets up a separate build environment (`requirements-derleme.txt`: PyInstaller), regenerates the data, runs the
tests, builds and checks the package. If `tools\PresentMon-*.exe` exists it is added to the package (Before / After
measurement). The official package's update signature is made with the maintainer's private key, which is not in this
repository; your own build is unsigned and does not mix with the official update channel.

Layout: `app/core` (settings, paths, language), `app/engine` (engine, backup, handlers, catalog), `app/scan` (read-only
scan), `app/ui` (Qt UI), `app/games`, `app/measure`; `data/` (settings catalog), `lang/` (translations), `tests/`,
`tools/`, `docs/`.

## Privacy

No telemetry, ads or analytics. Scan results, settings, backups and logs stay on your computer
(`%LOCALAPPDATA%\Forevermore`, backups in `%ProgramData%\Forevermore`). The only network use is the update check: you are
asked once; if you answer "Yes" it runs at most once a day (GitHub only, sends nothing, and the downloaded package's
signature is verified). If you answer "No" it never connects on its own. Change it in Settings > System.

## Contribute, security, support

- Contribute: [CONTRIBUTING.md](CONTRIBUTING.md)
- Report a vulnerability: [SECURITY.md](SECURITY.md) (do not open it as a public issue)
- Third-party components: [THIRD-PARTY-NOTICES.txt](THIRD-PARTY-NOTICES.txt)
- Optional: [buy me a coffee](https://buymeacoffee.com/forevermore). The app never asks.

## License

[MIT](LICENSE) © 2026 motherboardlabs. Third-party components keep their own licenses. The package no longer ships game
cover images.
