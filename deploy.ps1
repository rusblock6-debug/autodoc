# AutoDoc — one-button deploy
# Usage:
#   .\deploy.ps1            # обычный разворот (с кешем pip/npm — быстро)
#   .\deploy.ps1 -Clean     # чистая сборка образов без cache (баги вылезут как с нуля)
#   .\deploy.ps1 -Down       # остановить и удалить контейнеры стека
param(
    [switch]$Clean,
    [switch]$Down
)

$ErrorActionPreference = "Stop"
$env:DOCKER_BUILDKIT = "1"
$env:COMPOSE_DOCKER_CLI_BUILD = "1"

if ($Down) {
    Write-Host "==> Stopping autodoc stack..." -ForegroundColor Yellow
    docker compose down
    exit $LASTEXITCODE
}

if ($Clean) {
    Write-Host "==> Clean build (no image cache, pip/npm wheels still cached via BuildKit mounts)..." -ForegroundColor Cyan
    docker compose build --no-cache
    if ($LASTEXITCODE -ne 0) { Write-Host "BUILD FAILED" -ForegroundColor Red; exit 1 }
} else {
    Write-Host "==> Building (incremental)..." -ForegroundColor Cyan
    docker compose build
    if ($LASTEXITCODE -ne 0) { Write-Host "BUILD FAILED" -ForegroundColor Red; exit 1 }
}

Write-Host "==> Starting stack..." -ForegroundColor Cyan
docker compose up -d
if ($LASTEXITCODE -ne 0) { Write-Host "UP FAILED" -ForegroundColor Red; exit 1 }

Write-Host "==> Status:" -ForegroundColor Green
docker compose ps
Write-Host ""
Write-Host "Backend:  http://localhost:8888" -ForegroundColor Green
Write-Host "Frontend: http://localhost:3001" -ForegroundColor Green
Write-Host "Logs:     docker compose logs -f" -ForegroundColor DarkGray
