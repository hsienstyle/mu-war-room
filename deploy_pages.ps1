# 自動同步最新戰情室資料、GEMINI.md 規則、筆記與持倉至 GitHub (https://github.com/hsienstyle/mu-war-room)
$appDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$rootDir = Split-Path -Parent $appDir

# 若在舊版子目錄結構執行，自動將外層筆記與規則同步進來
if (Test-Path (Join-Path $rootDir "GEMINI.md")) {
    Copy-Item -Force (Join-Path $rootDir "GEMINI.md") $appDir
    Copy-Item -Force (Join-Path $rootDir "watchlist.md") $appDir
    if (Test-Path (Join-Path $rootDir "README.md")) {
        Copy-Item -Force (Join-Path $rootDir "README.md") $appDir
    }
    if (Test-Path (Join-Path $rootDir "notes")) {
        New-Item -ItemType Directory -Force -Path (Join-Path $appDir "notes") | Out-Null
        Copy-Item -Force (Join-Path $rootDir "notes\*.md") (Join-Path $appDir "notes")
    }
    if (Test-Path (Join-Path $rootDir "portfolio\trades.csv")) {
        New-Item -ItemType Directory -Force -Path (Join-Path $appDir "portfolio") | Out-Null
        Copy-Item -Force (Join-Path $rootDir "portfolio\trades.csv") (Join-Path $appDir "portfolio\trades.csv")
    }
}

Set-Location $appDir
git add index.html manifest.json MU_MUU_Widget.js portfolio_config.json cloud_daily_job.py GEMINI.md watchlist.md README.md notes/ portfolio/ .gitignore
$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm"
git commit -m "Sync workspace rules, notes, portfolio and iOS War Room ($timestamp)"
git push origin main

Write-Host "OK: Synced to GitHub (https://github.com/hsienstyle/mu-war-room) and GitHub Pages!" -ForegroundColor Green
