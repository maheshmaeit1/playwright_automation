param(
    [Parameter(Mandatory = $true)]
    [string]$OutputDir,

    [Parameter(Mandatory = $true)]
    [string]$Title,

    [string]$JsonReportPath,
    [string]$SourceHtmlPath,
    [string]$ReportLink,
    [string]$FallbackMessage = 'No report was generated for this run.'
)

$ErrorActionPreference = 'Stop'

New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null

function Write-SimpleHtml {
    param(
        [string]$PageTitle,
        [string]$BodyHtml
    )

    $html = @"
<!DOCTYPE html>
<html>
<head>
  <meta charset='utf-8' />
  <title>$PageTitle</title>
</head>
<body>
  $BodyHtml
</body>
</html>
"@

    Set-Content -Path (Join-Path $OutputDir 'index.html') -Value $html -Encoding UTF8
}

if ($SourceHtmlPath -and (Test-Path $SourceHtmlPath)) {
    Copy-Item $SourceHtmlPath (Join-Path $OutputDir 'index.html') -Force
    exit 0
}

if (-not $JsonReportPath -or -not (Test-Path $JsonReportPath)) {
    Write-SimpleHtml -PageTitle $Title -BodyHtml "<h1>$Title</h1><p>$FallbackMessage</p>"
    exit 0
}

$summary = @{ total = 0; passed = 0; failed = 0; skipped = 0 }
$failedRows = New-Object System.Collections.Generic.List[string]

function Add-Results {
    param(
        $Node,
        [string]$Trail = ''
    )

    if ($null -eq $Node) { return }

    $currentTrail = $Trail
    if ($Node.title) {
        $currentTrail = if ($Trail) { "$Trail > $($Node.title)" } else { [string]$Node.title }
    }

    if ($Node.specs) {
        foreach ($spec in $Node.specs) {
            foreach ($test in $spec.tests) {
                if (-not $test.results) { continue }

                $latest = $test.results[-1]
                $status = [string]$latest.status
                $summary.total++

                switch ($status) {
                    'passed' { $summary.passed++ }
                    'skipped' { $summary.skipped++ }
                    default   { $summary.failed++ }
                }

                if ($status -ne 'passed' -and $status -ne 'skipped') {
                    $name = [System.Net.WebUtility]::HtmlEncode([string]$spec.title)
                    $suite = [System.Net.WebUtility]::HtmlEncode([string]$currentTrail)
                    $message = ''

                    if ($latest.error -and $latest.error.message) {
                        $message = [System.Net.WebUtility]::HtmlEncode([string]$latest.error.message)
                    }

                    $failedRows.Add("<tr><td>$name</td><td>$suite</td><td>$status</td><td>$message</td></tr>") | Out-Null
                }
            }
        }
    }

    if ($Node.suites) {
        foreach ($child in $Node.suites) {
            Add-Results -Node $child -Trail $currentTrail
        }
    }
}

$report = Get-Content $JsonReportPath -Raw | ConvertFrom-Json
if ($report.suites) {
    foreach ($suite in $report.suites) {
        Add-Results -Node $suite
    }
}

$encodedTitle = [System.Net.WebUtility]::HtmlEncode($Title)
$linkHtml = if ($ReportLink) {
    "<p><a href='$ReportLink'>Open full Playwright report files</a></p>"
} else {
    ''
}

$failedTable = if ($failedRows.Count -gt 0) {
    "<table border='1' cellpadding='6' cellspacing='0'><tr><th>Test</th><th>Suite</th><th>Status</th><th>Error</th></tr>$($failedRows -join '')</table>"
} else {
    '<p>No failed tests in this run.</p>'
}

$body = @"
<h1>$encodedTitle</h1>
<p>This page is Jenkins-friendly and opens directly in the browser.</p>
$linkHtml
<h2>Summary</h2>
<table border='1' cellpadding='6' cellspacing='0'>
  <tr><th>Total</th><th>Passed</th><th>Failed</th><th>Skipped</th></tr>
  <tr><td>$($summary.total)</td><td>$($summary.passed)</td><td>$($summary.failed)</td><td>$($summary.skipped)</td></tr>
</table>
<h2>Failed tests</h2>
$failedTable
"@

Write-SimpleHtml -PageTitle $Title -BodyHtml $body
