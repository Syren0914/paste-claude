param([int]$TerminalProcessId = 0)
# This helper only reads the clipboard. Run in STA, hidden, with no profile.
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
Add-Type -AssemblyName System.Windows.Forms
Add-Type -TypeDefinition @'
using System.Runtime.InteropServices;
public static class ClipboardSequence {
    [DllImport("user32.dll")]
    public static extern uint GetClipboardSequenceNumber();
}
'@
for ($attempt = 0; $attempt -lt 5; $attempt++) {
    $image = $null
    try {
        $sequence = [ClipboardSequence]::GetClipboardSequenceNumber()
        if (-not [System.Windows.Forms.Clipboard]::ContainsImage()) {
            '{"kind":"other"}'
            exit 0
        }
        # Resolve the CLI below this terminal's shell, not another terminal's CLI.
        $client = 'other'
        if ($TerminalProcessId -gt 0) {
            $processes = @(Get-CimInstance Win32_Process -Property ProcessId, ParentProcessId, Name)
            $descendants = @($TerminalProcessId)
            for ($depth = 0; $depth -lt 16; $depth++) {
                $children = @($processes | Where-Object { $_.ParentProcessId -in $descendants -and $_.ProcessId -notin $descendants })
                if ($children.Count -eq 0) { break }
                $descendants += @($children.ProcessId)
            }
            $names = @($processes | Where-Object { $_.ProcessId -in $descendants } | ForEach-Object { $_.Name })
            if ('claude.exe' -in $names) { $client = 'claude' }
            elseif ('codex.exe' -in $names) { $client = 'codex' }
        }
        if ($client -ne 'other') {
            $kind = if ($sequence -eq [ClipboardSequence]::GetClipboardSequenceNumber()) { 'image' } else { 'changed' }
            @{ kind = $kind; client = $client } | ConvertTo-Json -Compress
            exit 0
        }
        $image = [System.Windows.Forms.Clipboard]::GetImage()
        if ($null -eq $image) { throw 'Clipboard image is temporarily unavailable.' }
        $directory = Join-Path ([System.IO.Path]::GetTempPath()) 'paste-claude'
        [System.IO.Directory]::CreateDirectory($directory) | Out-Null
        $imagePath = Join-Path $directory ('clipboard_' + [guid]::NewGuid().ToString('N') + '.png')
        $image.Save($imagePath, [System.Drawing.Imaging.ImageFormat]::Png)
        if ($sequence -ne [ClipboardSequence]::GetClipboardSequenceNumber()) {
            '{"kind":"changed"}'
            exit 0
        }
        @{ kind = 'image'; path = $imagePath } | ConvertTo-Json -Compress
        exit 0
    } catch {
        if ($attempt -eq 4) { throw }
        Start-Sleep -Milliseconds 50
    } finally {
        if ($null -ne $image) { $image.Dispose() }
    }
}
