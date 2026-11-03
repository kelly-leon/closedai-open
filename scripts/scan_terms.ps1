$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$terms = @(
  "(?i)\bKenya\b", "(?i)\bKenyan\b", "(?i)\bNairobi\b", "(?i)M-Pesa", "(?i)MPesa",
  "(?i)Safaricom", "(?i)\btill\b", "(?i)\bKSh\b", "(?i)\bKES\b",
  "(?i)\bShilling\b", "(?i)SCO\s*2", "(?i)mnu\.ac\.ke"
)
$secrets = @(
  "(?i)\bsk-ant-[A-Za-z0-9_-]+", "(?i)\beyJ[A-Za-z0-9_-]{8,}",
  "(?i)\bre_[A-Za-z0-9_-]{4,}", "(?i)\bpa-[A-Za-z0-9_-]+",
  "(?i)\bservice_role\b", "(?i)script\.google\.com/macros/s/",
  "(?i)postgresql://[^:\s]+:[^@\s]+@"
)

Get-ChildItem -LiteralPath $root -Recurse -Force -File |
  Where-Object {
    $_.FullName -notmatch '\\.git\\' -and
    $_.FullName -notmatch '\\node_modules\\' -and
    $_.FullName -notmatch '\\.next\\' -and
    $_.FullName -notmatch '\\scripts\\scan_terms\.ps1$'
  } |
  Sort-Object FullName |
  ForEach-Object {
    $relative = $_.FullName.Substring($root.Length).TrimStart('\')
    $lineNumber = 0
    foreach ($line in [System.IO.File]::ReadLines($_.FullName)) {
      $lineNumber++
      foreach ($pattern in ($terms + $secrets)) {
        if ([regex]::IsMatch($line, $pattern)) {
          Write-Output "${relative}:${lineNumber}"
          break
        }
      }
    }
  }
