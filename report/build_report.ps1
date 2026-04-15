param(
    [ValidateSet("quick", "full")]
    [string]$Profile = "quick",
    [int]$Trials = 30,
    [int]$Bits = 128,
    [int]$SampleSize = 12
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$PythonExe = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$LatexFile = Join-Path $PSScriptRoot "qsh_research_report.tex"

if (-not (Test-Path $PythonExe)) {
    Write-Error "Python venv not found at $PythonExe. Create it first: python -m venv .venv"
}

Write-Host "[1/2] Generating figures and CSV data..." -ForegroundColor Cyan
& $PythonExe (Join-Path $RepoRoot "scripts\generate_qkd_figures.py") `
    --profile $Profile `
    --trials $Trials `
    --bits $Bits `
    --sample-size $SampleSize

if ($LASTEXITCODE -ne 0) {
    Write-Error "Figure generation failed."
}

$PdfLatex = Get-Command pdflatex -ErrorAction SilentlyContinue
if (-not $PdfLatex) {
    Write-Warning "pdflatex not found in PATH. Figures/data are generated, but PDF compilation was skipped."
    Write-Host "Install TeX Live or MiKTeX, then run:" -ForegroundColor Yellow
    Write-Host "  cd `"$PSScriptRoot`"; pdflatex qsh_research_report.tex; pdflatex qsh_research_report.tex"
    exit 0
}

Push-Location $PSScriptRoot
try {
    Write-Host "[2/2] Building PDF report..." -ForegroundColor Cyan
    & pdflatex -interaction=nonstopmode (Split-Path -Leaf $LatexFile) | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Error "First pdflatex run failed."
    }
    & pdflatex -interaction=nonstopmode (Split-Path -Leaf $LatexFile) | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Second pdflatex run failed."
    }
}
finally {
    Pop-Location
}

Write-Host "Report build complete: $PSScriptRoot\qsh_research_report.pdf" -ForegroundColor Green
