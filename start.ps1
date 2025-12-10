# Channel Manager - Startup Script
# This script starts both the Discord bot and the web dashboard

Write-Host "🤖 Starting Channel Manager..." -ForegroundColor Cyan
Write-Host ""

# Check if .env exists
if (-not (Test-Path ".env")) {
    Write-Host "❌ .env file not found!" -ForegroundColor Red
    Write-Host "📝 Please copy .env.example to .env and configure it." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Run: Copy-Item .env.example .env" -ForegroundColor Yellow
    exit 1
}

# Check if virtual environment exists
if (-not (Test-Path "venv")) {
    Write-Host "📦 Creating virtual environment..." -ForegroundColor Yellow
    python -m venv venv
}

# Activate virtual environment
Write-Host "🔧 Activating virtual environment..." -ForegroundColor Yellow
& ".\venv\Scripts\Activate.ps1"

# Install dependencies
Write-Host "📥 Installing dependencies..." -ForegroundColor Yellow
pip install -r requirements.txt --quiet

Write-Host ""
Write-Host "✅ Setup complete!" -ForegroundColor Green
Write-Host ""
Write-Host "🚀 Starting services..." -ForegroundColor Cyan
Write-Host ""

# Start bot in background job
Write-Host "🤖 Starting Discord bot..." -ForegroundColor Green
$botJob = Start-Job -ScriptBlock {
    Set-Location $using:PWD
    & ".\venv\Scripts\python.exe" -m src.bot
}

# Wait a moment for bot to initialize
Start-Sleep -Seconds 2

# Start dashboard in background job
Write-Host "🌐 Starting web dashboard..." -ForegroundColor Green
$dashJob = Start-Job -ScriptBlock {
    Set-Location $using:PWD
    & ".\venv\Scripts\python.exe" -m src.web.dashboard
}

Write-Host ""
Write-Host "✅ Both services started!" -ForegroundColor Green
Write-Host ""
Write-Host "📊 Status:" -ForegroundColor Cyan
Write-Host "   🤖 Discord Bot: Running (Job ID: $($botJob.Id))" -ForegroundColor White
Write-Host "   🌐 Dashboard: http://localhost:5000 (Job ID: $($dashJob.Id))" -ForegroundColor White
Write-Host ""
Write-Host "📝 Monitoring output..." -ForegroundColor Yellow
Write-Host "   Press Ctrl+C to stop all services" -ForegroundColor Yellow
Write-Host ""

# Monitor jobs and show output
try {
    while ($true) {
        # Check bot output
        $botOutput = Receive-Job -Job $botJob
        if ($botOutput) {
            Write-Host "[BOT] $botOutput" -ForegroundColor Blue
        }
        
        # Check dashboard output
        $dashOutput = Receive-Job -Job $dashJob
        if ($dashOutput) {
            Write-Host "[DASH] $dashOutput" -ForegroundColor Magenta
        }
        
        # Check if jobs are still running
        if ($botJob.State -ne "Running") {
            Write-Host "⚠️ Bot job stopped!" -ForegroundColor Red
            break
        }
        if ($dashJob.State -ne "Running") {
            Write-Host "⚠️ Dashboard job stopped!" -ForegroundColor Red
            break
        }
        
        Start-Sleep -Milliseconds 500
    }
}
finally {
    Write-Host ""
    Write-Host "🛑 Stopping services..." -ForegroundColor Yellow
    Stop-Job -Job $botJob -ErrorAction SilentlyContinue
    Stop-Job -Job $dashJob -ErrorAction SilentlyContinue
    Remove-Job -Job $botJob -Force -ErrorAction SilentlyContinue
    Remove-Job -Job $dashJob -Force -ErrorAction SilentlyContinue
    Write-Host "✅ All services stopped" -ForegroundColor Green
}
