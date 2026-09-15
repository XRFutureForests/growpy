# Drive one PVE graph's Export click from outside the editor. Called by growpy-pve-export;
# the graph must already be open in its asset editor and executed (the Python side waits for that).
#
# Sequence: posted press on the toolbar Export button (focus only) -> posted Ctrl+E (the toolkit's
# Export command) -> 'Modify Export Settings' dialog: Batch + Export via UIA Invoke -> optional
# 'WARNING: Assets will be overwritten' prompt: Continue via UIA Invoke -> wait for the log.
# Works with the workstation locked: nothing here needs focus, foreground or the physical cursor.
param(
  [Parameter(Mandatory)][string]$WindowTitle,   # asset editor window title (= asset name)
  [Parameter(Mandatory)][string]$LogPath,
  [int]$ToolbarX = 435, [int]$ToolbarY = 83,     # offset from the window's Win32 rect origin to the toolbar Export button
  [int]$DialogSec = 120,
  [int]$OverwriteSec = 25,
  [int]$ExpectedMeshes = 0,                      # >0: wait until this many 'Mesh exported successfully' lines
  [int]$ExportSec = 3600,
  [switch]$LocateToolbar                         # find the toolbar button through UIA instead of the offsets (slow, ~1 min)
)
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\pve_export_uia.ps1"
$sw = [Diagnostics.Stopwatch]::StartNew()
function Log($m) { Write-Output ("[{0,7:N1}s] {1}" -f $sw.Elapsed.TotalSeconds, $m) }
function Read-LogFrom([long]$offset) {
  $fs = [IO.File]::Open($LogPath, 'Open', 'Read', 'ReadWrite'); $fs.Seek($offset, 'Begin') | Out-Null
  $sr = New-Object IO.StreamReader($fs); $t = $sr.ReadToEnd(); $sr.Close(); return $t
}

$pid_ = Get-UEPid
$logStart = (Get-Item $LogPath).Length

# 1. asset editor window + toolbar button (window-relative, no UIA needed)
$hwnd = Wait-UEHwnd $pid_ $WindowTitle 30
if ($hwnd -eq [IntPtr]::Zero) { Log "NOWINDOW '$WindowTitle'"; exit 2 }
$r = New-Object UEW32+RECT; [void][UEW32]::GetWindowRect($hwnd, [ref]$r)
$bx = $r.L + $ToolbarX; $by = $r.T + $ToolbarY
Log "window '$WindowTitle' rect=($($r.L),$($r.T))-($($r.R),$($r.B)); toolbar Export assumed at ($bx,$by)"
if ($LocateToolbar) {
  $win = Get-SlateElement $hwnd 90
  $btn = if ($win) { Find-Button $win 'Export' 180 } else { $null }
  if (-not $btn) { Log "NOTOOLBAR: no 'Export' button found in '$WindowTitle' through UIA"; exit 2 }
  $br = $btn.Current.BoundingRectangle
  $bx = [int]($br.X + $br.Width / 2); $by = [int]($br.Y + $br.Height / 2)
  Log "toolbar Export located at $(Format-Rect $br) -> window offset ($($bx - $r.L),$($by - $r.T))"
}

# 2. focus the toolbar button with a posted press, then the toolkit chord
[UEW32]::PostPress($hwnd, $bx, $by)
Start-Sleep -Milliseconds 400
[UEW32]::PostCtrlE($hwnd)
Log "posted focus-press + Ctrl+E"

# 3. export-settings dialog (this process holds the UIA element so the accessible tree stays alive)
$dh = Wait-UEHwnd $pid_ 'Modify Export Settings' $DialogSec
if ($dh -eq [IntPtr]::Zero) { Log "NODIALOG: no 'Modify Export Settings' window within $DialogSec s (is Slate focus inside the PVE editor?)"; exit 3 }
$dlg = Get-SlateElement $dh 90
if (-not $dlg) { Log "NOTREE: dialog never reported FrameworkId=Slate (Accessibility.Enable off?)"; exit 3 }
Log "export dialog up after $($sw.Elapsed.TotalSeconds.ToString('N1')) s"
$batch = $null; $deadline = (Get-Date).AddSeconds(60)
while (-not $batch -and (Get-Date) -lt $deadline) {
  $batch = Find-NamedShallow $dlg 'Batch' @([System.Windows.Automation.ControlType]::CheckBox, [System.Windows.Automation.ControlType]::RadioButton, [System.Windows.Automation.ControlType]::Button, [System.Windows.Automation.ControlType]::Custom)
  if (-not $batch) { Start-Sleep -Milliseconds 700 }
}
if ($batch) { Log ("Batch " + (Set-Selectable $batch)) } else { Log "Batch element not found; dialog default applies (Batch unless a node is selected)" }
$exp = Find-Button $dlg 'Export' 60
if (-not $exp) { Log "NO 'Export' button in dialog"; exit 4 }
Log ("dialog Export -> " + (Invoke-Element $exp))

# 4. overwrite prompt (PackagesDialog; only when Replace-policy targets already exist)
$oh = Wait-UEHwnd $pid_ 'WARNING: Assets will be overwritten' $OverwriteSec
if ($oh -ne [IntPtr]::Zero) {
  $od = Get-SlateElement $oh 60
  $cont = if ($od) { Find-Button $od 'Continue' 60 } else { $null }
  if ($cont) { Log ("overwrite Continue -> " + (Invoke-Element $cont)) } else { Log "overwrite prompt up but no 'Continue' button found"; exit 5 }
} else { Log "no overwrite prompt" }

# 5. wait for the export (it runs synchronously on the game thread after the dialog closes)
$deadline = (Get-Date).AddSeconds($ExportSec)
do {
  Start-Sleep -Seconds 3
  $txt = Read-LogFrom $logStart
  $started = ($txt -match 'Export Started')
  $done = ([regex]::Matches($txt, 'Mesh exported successfully')).Count
  $busy = [UEW32]::IsWindow($dh) -or ($oh -ne [IntPtr]::Zero -and [UEW32]::IsWindow($oh))
  $waiting = $busy -or -not $started -or ($ExpectedMeshes -gt 0 -and $done -lt $ExpectedMeshes) -or ($ExpectedMeshes -le 0 -and $done -eq 0)
} while ($waiting -and (Get-Date) -lt $deadline)
Log "export started=$started meshes=$done expected=$ExpectedMeshes"
foreach ($m in [regex]::Matches($txt, 'Mesh exported successfully "([^"]+)"')) { Log ("  exported " + $m.Groups[1].Value) }
foreach ($m in [regex]::Matches($txt, '(LogProceduralVegetationEditor|LogProceduralVegetation): Error: [^\r\n]*')) { Log ("  " + $m.Value) }
if (-not $started) { exit 6 }
if ($ExpectedMeshes -gt 0 -and $done -lt $ExpectedMeshes) { exit 7 }
exit 0
