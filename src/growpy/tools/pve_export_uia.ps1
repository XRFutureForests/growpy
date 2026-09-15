# UI Automation + Win32 helpers for driving the Unreal editor's Slate UI from outside.
# Dot-source this file. Requires `Accessibility.Enable 1` in the editor (set by growpy-pve-export).
#
# Facts these helpers rely on (UE 5.8 source, verified 2026-09-15):
#  - Slate answers Windows UIA once Accessibility.Enable is 1; a UIA Invoke runs SButton::ExecuteOnClick
#    on the game thread and BLOCKS the caller until the handler returns, and UE serialises UIA calls, so
#    never Invoke a button whose handler opens a modal dialog or runs an export (use the posted chord).
#  - The accessible tree is torn down when the last UIA client releases its references
#    (FWindowsUIAManager::OnWidgetProviderRemoved), so one long-lived process must hold an element for
#    the whole run; it is rebuilt at Slate.AccessibleWidgetsProcessedPerTick widgets per tick.
#  - Mouse-button messages carry their position in lParam (WindowsApplication.cpp), so a posted
#    WM_LBUTTONDOWN/UP presses and focuses a button, but SButton only fires when the PHYSICAL cursor
#    hovers it, so posted clicks cannot execute buttons; posted key messages have no such dependency and
#    WindowsApplication.cpp tracks modifier state from the messages themselves (posted Ctrl counts).
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
$script:A = [System.Windows.Automation.AutomationElement]
$script:TS = [System.Windows.Automation.TreeScope]
$script:Walker = [System.Windows.Automation.TreeWalker]::RawViewWalker

Add-Type @"
using System; using System.Text; using System.Runtime.InteropServices;
public static class UEW32 {
  public delegate bool EnumProc(IntPtr h, IntPtr l);
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int L, T, R, B; }
  [StructLayout(LayoutKind.Sequential)] public struct POINT { public int X, Y; }
  [DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc p, IntPtr l);
  [DllImport("user32.dll", CharSet = CharSet.Unicode)] public static extern int GetWindowTextW(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
  [DllImport("user32.dll")] public static extern bool IsWindow(IntPtr h);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern bool ScreenToClient(IntPtr h, ref POINT p);
  [DllImport("user32.dll")] public static extern bool PostMessageW(IntPtr h, uint msg, IntPtr w, IntPtr l);
  public static IntPtr FindByTitle(uint pid, string title) {
    IntPtr found = IntPtr.Zero;
    EnumWindows((h, l) => { uint p; GetWindowThreadProcessId(h, out p); if (p != pid || !IsWindowVisible(h)) return true;
      var sb = new StringBuilder(512); GetWindowTextW(h, sb, 512); if (sb.ToString() == title) { found = h; return false; } return true; }, IntPtr.Zero);
    return found; }
  public static IntPtr LP(int x, int y) { return (IntPtr)((y << 16) | (x & 0xFFFF)); }
  // press + release at a screen point: gives the widget Slate keyboard focus without executing it
  public static void PostPress(IntPtr h, int sx, int sy) {
    var p = new POINT { X = sx, Y = sy }; ScreenToClient(h, ref p); var lp = LP(p.X, p.Y);
    PostMessageW(h, 0x0200, IntPtr.Zero, lp); System.Threading.Thread.Sleep(80);
    PostMessageW(h, 0x0201, (IntPtr)1, lp); System.Threading.Thread.Sleep(80);
    PostMessageW(h, 0x0202, IntPtr.Zero, lp); }
  public static void PostKey(IntPtr h, int vk, int scan, bool down) {
    long lp = 1L | ((long)scan << 16); if (!down) lp |= (1L << 30) | (1L << 31);
    PostMessageW(h, down ? 0x0100u : 0x0101u, (IntPtr)vk, (IntPtr)lp); }
  // Ctrl+E = FPVEditorCommands::Export; routed by SStandaloneAssetEditorToolkitHost::OnKeyDown
  public static void PostCtrlE(IntPtr h) {
    PostKey(h, 0x11, 0x1D, true); System.Threading.Thread.Sleep(40);
    PostKey(h, 0x45, 0x12, true); System.Threading.Thread.Sleep(60);
    PostKey(h, 0x45, 0x12, false); System.Threading.Thread.Sleep(40);
    PostKey(h, 0x11, 0x1D, false); }
}
"@

function Get-UEPid { [uint32](Get-Process UnrealEditor -ErrorAction Stop | Select-Object -First 1).Id }

function Wait-UEHwnd([uint32]$ProcessId, [string]$Title, [int]$Sec) {
  $deadline = (Get-Date).AddSeconds($Sec)
  do {
    $h = [UEW32]::FindByTitle($ProcessId, $Title)
    if ($h -ne [IntPtr]::Zero) { return $h }
    Start-Sleep -Milliseconds 400
  } while ((Get-Date) -lt $deadline)
  return [IntPtr]::Zero
}

function Get-SlateElement([IntPtr]$Hwnd, [int]$Sec = 90) {
  # UIA answers with the Win32 fallback (FrameworkId 'Win32') until the accessible tree exists
  $deadline = (Get-Date).AddSeconds($Sec)
  do {
    $el = $A::FromHandle($Hwnd)
    if ($el.Current.FrameworkId -eq 'Slate') { return $el }
    Start-Sleep -Milliseconds 800
  } while ((Get-Date) -lt $deadline)
  return $null
}

$script:HeavyClasses = @('SDetailsView', 'SListView', 'STreeView', 'STileView', 'SMultiLineEditableText', 'SGraphPanel', 'SViewport', 'SLevelViewport')

function Find-NamedShallow($Root, [string]$Name, $Types, [int]$MaxDepth = 12) {
  # breadth-first, skipping heavy subtrees; every property read is a game-thread round trip
  $queue = New-Object System.Collections.Generic.Queue[object]
  $queue.Enqueue(@($Root, 0))
  while ($queue.Count -gt 0) {
    $item = $queue.Dequeue(); $el = $item[0]; $depth = $item[1]
    $k = $Walker.GetFirstChild($el)
    while ($k) {
      $c = $k.Current
      if ($c.Name -eq $Name -and ($Types -contains $c.ControlType)) { return $k }
      if ($depth -lt $MaxDepth -and ($HeavyClasses -notcontains $c.ClassName)) { $queue.Enqueue(@($k, $depth + 1)) }
      $k = $Walker.GetNextSibling($k)
    }
  }
  return $null
}

function Find-Named($Root, [string]$Name, $Type) {
  $cond = New-Object System.Windows.Automation.AndCondition(
    (New-Object System.Windows.Automation.PropertyCondition($A::ControlTypeProperty, $Type)),
    (New-Object System.Windows.Automation.PropertyCondition($A::NameProperty, $Name)))
  # leading comma keeps PowerShell from unrolling a one-element collection
  return ,$Root.FindAll($TS::Descendants, $cond)
}

function Find-Button($Root, [string]$Name, [int]$Sec) {
  $deadline = (Get-Date).AddSeconds($Sec)
  do {
    $b = Find-NamedShallow $Root $Name @([System.Windows.Automation.ControlType]::Button)
    if ($b) { return $b }
    $hits = Find-Named $Root $Name ([System.Windows.Automation.ControlType]::Button)
    if ($hits.Count -gt 0) { return $hits.Item(0) }
    Start-Sleep -Milliseconds 700
  } while ((Get-Date) -lt $deadline)
  return $null
}

function Invoke-Element($El) {
  try { $El.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern).Invoke(); return "INVOKED" }
  catch { return "INVOKE-CALL-ENDED: $($_.Exception.GetType().Name): $($_.Exception.Message)" }
}

function Set-Selectable($El) {
  # segmented-control slots are SCheckBox (TogglePattern); accept the other selection patterns too
  $c = $El.Current
  $tp = $null; $sp = $null; $ip = $null
  try { $tp = $El.GetCurrentPattern([System.Windows.Automation.TogglePattern]::Pattern) } catch {}
  try { $sp = $El.GetCurrentPattern([System.Windows.Automation.SelectionItemPattern]::Pattern) } catch {}
  try { $ip = $El.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern) } catch {}
  if ($tp) { if ($tp.Current.ToggleState -ne 'On') { $tp.Toggle() }; return "[$($c.ClassName)] toggle -> $($tp.Current.ToggleState)" }
  if ($sp) { if (-not $sp.Current.IsSelected) { $sp.Select() }; return "[$($c.ClassName)] selected -> $($sp.Current.IsSelected)" }
  if ($ip) { $ip.Invoke(); return "[$($c.ClassName)] invoked" }
  return "[$($c.ClassName)] has no actionable pattern"
}

function Format-Rect($r) { if ([double]::IsInfinity($r.X)) { return "(none)" }; "({0},{1} {2}x{3})" -f [int]$r.X, [int]$r.Y, [int]$r.Width, [int]$r.Height }
