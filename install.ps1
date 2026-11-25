# Installs Daytag for the person running it. No admin rights. Double-click "Install Daytag.cmd" to run this.
# It finds or installs Python, puts "Daytag" in the Start menu, starts Daytag at every sign-in and opens the
# setup wizard. Everything else (GitHub, calendar, Slack) the wizard does with buttons.
#
#   install.ps1                 the normal install
#   install.ps1 -NoAutostart    without starting at sign-in
#   install.ps1 -Remove         take the Start menu and sign-in entries away again
#
# This file is ASCII on purpose: Windows PowerShell 5.1 reads a file without a byte order mark as ANSI.
param([switch]$NoAutostart, [switch]$Remove)
$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$menu = Join-Path ([Environment]::GetFolderPath('Programs')) 'Daytag.lnk'
$startup = Join-Path ([Environment]::GetFolderPath('Startup')) 'Daytag server.lnk'

if ($Remove) {
    foreach ($p in @($menu, $startup)) { if (Test-Path $p) { Remove-Item $p -Confirm:$false; "Removed $p" } }
    [Environment]::SetEnvironmentVariable('DAYTAG_PYTHON', $null, 'User')
    'Your settings stay, in the folder .daytag in your home folder. Delete .daytag to start over.'
    return
}

function Update-PathFromSystem {
    # A program installed a moment ago is only on the PATH of new windows. This window reads it fresh.
    $env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' + [Environment]::GetEnvironmentVariable('Path', 'User')
}

function Find-Python {
    # The Microsoft Store placeholder answers "python" without being Python, so every candidate is asked a question.
    $candidates = @('python', 'py')
    $candidates += @(Get-ChildItem -Path (Join-Path $env:LOCALAPPDATA 'Programs\Python') -Filter python.exe -Recurse -ErrorAction SilentlyContinue | ForEach-Object { $_.FullName })
    foreach ($c in $candidates) {
        try {
            $exe = (& $c -c "import sys; print(sys.executable if sys.version_info >= (3, 9) else '')" 2>$null)
            if ($exe -and (Test-Path $exe.Trim())) { return $exe.Trim() }
        } catch { }
    }
    return ''
}

# 1. Python 3.9 or newer, installed for this user only when it is missing.
$python = Find-Python
if (-not $python) {
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        'Python is missing. Installing it for you, this takes about a minute...'
        & winget install --id Python.Python.3.12 -e --scope user --silent --accept-package-agreements --accept-source-agreements | Out-Null
        Update-PathFromSystem
        $python = Find-Python
    }
}
if (-not $python) {
    Write-Host 'Python could not be installed by itself. Install Python 3 from https://www.python.org/downloads/ and double-click "Install Daytag" again.' -ForegroundColor Yellow
    exit 1
}
"Python: $python"
# Daytag's start scripts use this exact Python, whatever the PATH says.
[Environment]::SetEnvironmentVariable('DAYTAG_PYTHON', $python, 'User')
$env:DAYTAG_PYTHON = $python

# 2. Start menu entry, and the start at sign-in unless switched off.
$shell = New-Object -ComObject WScript.Shell
$lnk = $shell.CreateShortcut($menu)
$lnk.TargetPath = Join-Path $here 'daytag.cmd'
$lnk.WorkingDirectory = $here
$lnk.WindowStyle = 7
$icon = Join-Path $here 'desktop\icon.ico'
if (Test-Path $icon) { $lnk.IconLocation = $icon }
$lnk.Description = 'Daytag: what needs you today'
$lnk.Save()
"Start menu: Daytag"
if (-not $NoAutostart) {
    $auto = $shell.CreateShortcut($startup)
    $auto.TargetPath = 'wscript.exe'
    $auto.Arguments = '"' + (Join-Path $here 'start-hidden.vbs') + '"'
    $auto.WorkingDirectory = $here
    $auto.Save()
    'Starts by itself when you sign in to Windows.'
}

# 3. Open it. The first start shows the setup wizard. An older copy that still runs is stopped first.
$pythonw = Join-Path (Split-Path -Parent $python) 'pythonw.exe'
if (-not (Test-Path $pythonw)) { $pythonw = $python }
Start-Process -FilePath $pythonw -ArgumentList ('"' + (Join-Path $here 'launcher.py') + '"'), '--replace'
'Daytag opens in a moment and walks you through the rest.'
