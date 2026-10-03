# Run one check of a built Lightning executable and fail loudly unless it passed.
#
# A check passes only when the process exits with code 0 within the time limit AND writes a JSON
# report whose "ok" is true. The report is printed either way, so a failure in CI shows its stage.
#
#   pwsh packaging/run_check.ps1 -Exe <path to exe> -Report <json path> -Arguments --self-check
param(
    [Parameter(Mandatory = $true)][string] $Exe,
    [Parameter(Mandatory = $true)][string] $Report,
    [string[]] $Arguments = @(),
    [int] $TimeoutSeconds = 180
)
$ErrorActionPreference = 'Stop'

$exePath = (Resolve-Path -LiteralPath $Exe).Path
$reportPath = [System.IO.Path]::GetFullPath($Report)
$label = "$(Split-Path -Leaf $exePath) $($Arguments -join ' ')"
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $reportPath) | Out-Null
if (Test-Path -LiteralPath $reportPath) { Remove-Item -LiteralPath $reportPath -Force }

# Process.Start without the shell keeps the exit code of a GUI program that has already ended, and
# ArgumentList quotes each argument (a path with spaces stays one argument).
$start = [System.Diagnostics.ProcessStartInfo]::new($exePath)
$start.UseShellExecute = $false
foreach ($argument in @($Arguments) + @('--report', $reportPath)) { $start.ArgumentList.Add($argument) }
Write-Host "Running: $exePath $($start.ArgumentList -join ' ')"
$process = [System.Diagnostics.Process]::Start($start)
if (-not $process.WaitForExit($TimeoutSeconds * 1000)) {
    $process.Kill($true)  # the whole tree, WebView2 helpers included
    throw "$label did not finish within $TimeoutSeconds seconds"
}
$process.WaitForExit()
$exitCode = $process.ExitCode

if (-not (Test-Path -LiteralPath $reportPath)) {
    throw "$label exited with code $exitCode and wrote no report"
}
$text = Get-Content -LiteralPath $reportPath -Raw
Write-Host $text
$result = $text | ConvertFrom-Json
if ($exitCode -ne 0 -or $result.ok -ne $true) {
    throw "$label failed (exit code $exitCode, ok=$($result.ok))"
}
Write-Host "Passed: $label"
