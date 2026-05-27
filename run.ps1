param(
    [switch]$Stop
)

$ProjectRoot = $PSScriptRoot

# ── 停止 ──
if ($Stop) {
    Write-Host "正在停止服务..." -ForegroundColor Yellow
    Get-CimInstance Win32_Process | Where-Object {
        $_.CommandLine -and $_.CommandLine -like "*$ProjectRoot*"
    } | ForEach-Object {
        try { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue } catch {}
    }
    9001, 9002, 9003, 9900 | ForEach-Object {
        Get-NetTCPConnection -LocalPort $_ -State Listen -ErrorAction SilentlyContinue |
        ForEach-Object {
            try { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue } catch {}
        }
    }
    Write-Host "已停止所有服务" -ForegroundColor Green
    exit 0
}

# ── 检测 Python ──
$Python = if (Test-Path "$ProjectRoot\.venv\Scripts\python.exe") { "$ProjectRoot\.venv\Scripts\python.exe" }
          elseif (Get-Command python -ErrorAction SilentlyContinue) { "python" }
          else { Write-Host "未找到 Python" -ForegroundColor Red; exit 1 }

# ── 启动 3 个 MCP 服务（隐藏窗口）──
@(
    @{Name="system";   Port=9001},
    @{Name="network";  Port=9002},
    @{Name="docker";   Port=9003}
) | ForEach-Object {
    $script = "$ProjectRoot\mcp_servers\$($_.Name)_server.py"
    $logDir = "$ProjectRoot\logs"
    if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir -Force | Out-Null }
    Start-Process -FilePath $Python -ArgumentList $script -WindowStyle Hidden `
        -RedirectStandardOutput "$logDir\$($_.Name).log" -RedirectStandardError "$logDir\$($_.Name).err.log"
    Write-Host "[MCP] $($_.Name)_server (端口 $($_.Port))" -ForegroundColor Cyan
}

Start-Sleep -Seconds 2

# ── 启动 FastAPI（前台）──
Write-Host ""
Write-Host "访问地址:" -ForegroundColor Green
Write-Host "  Web UI:   http://localhost:9900/frontend/index.html" -ForegroundColor Green
Write-Host "  API 文档: http://localhost:9900/docs" -ForegroundColor Green
Write-Host "  停止服务: .\run.ps1 -Stop" -ForegroundColor Green
Write-Host ""

& $Python -m uvicorn app.main:app --host 127.0.0.1 --port 9900 --reload --reload-dir "$ProjectRoot\app"
