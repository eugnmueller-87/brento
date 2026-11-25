; The Windows installer: one file, for the person running it, without administrator rights.
; Built by packaging/build.py, which first puts Daytag, its own Python and the GitHub program into the Stage folder.
; "Preview" makes a test build with its own name and folder that never touches an installed Daytag.
#ifndef AppVersion
  #error AppVersion is missing. Build with packaging/build.py windows
#endif
#ifndef Stage
  #error Stage is missing. Build with packaging/build.py windows
#endif
#ifndef Output
  #error Output is missing. Build with packaging/build.py windows
#endif

#ifdef Preview
  #define Name "Daytag Preview"
  #define Id "{{C0406062-FF60-4AC4-8CEC-3B3928E4F9EE}"
  #define OutFile "Daytag-Windows-Preview"
#else
  #define Name "Daytag"
  #define Id "{{7DCBEF36-B58A-41A6-9D24-4C28D2519BA8}"
  #define OutFile "Daytag-Windows"
#endif

[Setup]
AppId={#Id}
AppName={#Name}
AppVersion={#AppVersion}
AppVerName={#Name} {#AppVersion}
AppPublisher=Daytag
AppPublisherURL=https://github.com/eugnmueller-87/daytag
AppSupportURL=https://github.com/eugnmueller-87/daytag/issues
AppUpdatesURL=https://github.com/eugnmueller-87/daytag/releases/latest
VersionInfoVersion={#AppVersion}
VersionInfoProductName={#Name}
VersionInfoDescription={#Name} Setup
DefaultDirName={localappdata}\Programs\{#Name}
DisableDirPage=yes
DisableProgramGroupPage=yes
DisableWelcomePage=no
DisableReadyPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
CloseApplications=no
RestartApplications=no
ShowLanguageDialog=no
LanguageDetectionMethod=uilanguage
WizardStyle=modern
WizardImageFile=wizard-large.png
WizardSmallImageFile=wizard-small.png
SetupIconFile=daytag.ico
UninstallDisplayIcon={app}\daytag.ico
UninstallDisplayName={#Name}
OutputDir={#Output}
OutputBaseFilename={#OutFile}
Compression=lzma2/max
SolidCompression=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "german"; MessagesFile: "compiler:Languages\German.isl"

[Messages]
english.WelcomeLabel1=Welcome to Daytag
english.WelcomeLabel2=One screen that tells you what needs you today: your tasks, your board and your meetings.%n%nDaytag brings everything it needs. It installs only for you, so Windows asks for no administrator password.%n%nWhen it is done, Daytag opens and asks one question per page. You can skip every one of them.%n%nDaytag runs on this computer, keeps its settings here and only reads: it never changes a note, a card or an appointment. Notes go to Claude and messages to Slack only if you switch that on.
english.WizardSelectTasks=Two small choices
english.SelectTasksDesc=You can change both later.
english.SelectTasksLabel2=If you are not sure, leave both ticked. Then click Install.
english.FinishedHeadingLabel=Daytag is ready
english.FinishedLabelNoIcons=Daytag opens and walks you through the rest.%n%nTo open it later, press the Windows key, type Daytag and press Enter.
english.FinishedLabel=Daytag opens and walks you through the rest.%n%nTo open it later, press the Windows key, type Daytag and press Enter.
english.ClickFinish=Now click Finish.
english.ConfirmUninstall=Remove %1 from this computer?%n%nYour notes, your board and your calendar stay as they are.
english.UninstalledAll=%1 is removed.%n%nIf you signed in to GitHub, that sign-in stays in Windows. You can take it back under github.com/settings/applications.
german.WelcomeLabel1=Willkommen bei Daytag
german.WelcomeLabel2=Ein Bildschirm, der dir zeigt, was dich heute braucht: deine Aufgaben, dein Board und deine Termine.%n%nDaytag bringt alles mit, was es braucht. Es wird nur für dich installiert, darum fragt Windows nicht nach einem Administrator-Kennwort.%n%nDanach öffnet sich Daytag und stellt eine Frage pro Seite. Jede davon kannst du überspringen.%n%nDaytag läuft auf diesem Computer, behält seine Einstellungen hier und liest nur: Es ändert nie eine Notiz, eine Karte oder einen Termin. Notizen gehen an Claude und Meldungen an Slack nur, wenn du das einschaltest. Die Oberfläche ist auf Englisch.
german.ClickNext=Klicke auf Weiter.
german.WizardSelectTasks=Zwei kleine Entscheidungen
german.SelectTasksDesc=Beides kannst du später ändern.
german.SelectTasksLabel2=Wenn du unsicher bist, lass beide Häkchen gesetzt. Klicke dann auf Installieren.
german.FinishedHeadingLabel=Daytag ist bereit
german.FinishedLabelNoIcons=Daytag öffnet sich und führt dich durch den Rest.%n%nSpäter öffnen: Windows-Taste drücken, Daytag tippen, Eingabetaste.
german.FinishedLabel=Daytag öffnet sich und führt dich durch den Rest.%n%nSpäter öffnen: Windows-Taste drücken, Daytag tippen, Eingabetaste.
german.ClickFinish=Klicke jetzt auf Fertigstellen.
german.ConfirmUninstall=%1 von diesem Computer entfernen?%n%nDeine Notizen, dein Board und dein Kalender bleiben, wie sie sind.
german.UninstalledAll=%1 ist entfernt.%n%nWenn du dich bei GitHub angemeldet hast, bleibt diese Anmeldung in Windows. Zurücknehmen kannst du sie unter github.com/settings/applications.

[CustomMessages]
english.Autostart=Start Daytag when I sign in to Windows
english.Desktop=Put Daytag on the desktop
english.OpenNow=Open Daytag now
english.About=Daytag: what needs you today
english.StillRunning=Daytag could not be closed. Restart the computer and open this file again.
english.DeleteSettings=Delete the settings of Daytag too?%n%nThat is the folder %1 with your calendar link, the Slack link and the paired phones. If you may come back to Daytag, keep them.
german.Autostart=Daytag bei der Anmeldung an Windows starten
german.Desktop=Daytag auf den Desktop legen
german.OpenNow=Daytag jetzt öffnen
german.About=Daytag: was dich heute braucht
german.StillRunning=Daytag ließ sich nicht schließen. Starte den Computer neu und öffne diese Datei noch einmal.
german.DeleteSettings=Auch die Einstellungen von Daytag löschen?%n%nDas ist der Ordner %1 mit deinem Kalenderlink, dem Slack-Link und den gekoppelten Handys. Wenn du vielleicht zu Daytag zurückkommst, behalte sie.

[Tasks]
#ifndef Preview
Name: "autostart"; Description: "{cm:Autostart}"
#endif
Name: "desktop"; Description: "{cm:Desktop}"

[InstallDelete]
; Files of an older version that no longer exist must not stay behind and be loaded.
Type: filesandordirs; Name: "{app}\python"
Type: filesandordirs; Name: "{app}\app\web"
Type: filesandordirs; Name: "{app}\app\__pycache__"
Type: files; Name: "{app}\app\*.py"
#ifndef Preview
; The start at sign-in that the older ZIP installer made would start the older copy.
Type: files; Name: "{userstartup}\Daytag server.lnk"
#endif

[Files]
Source: "{#Stage}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{userprograms}\{#Name}"; Filename: "{app}\python\pythonw.exe"; Parameters: """{app}\app\launcher.py"""; WorkingDir: "{app}\app"; IconFilename: "{app}\daytag.ico"; Comment: "{cm:About}"
Name: "{userdesktop}\{#Name}"; Filename: "{app}\python\pythonw.exe"; Parameters: """{app}\app\launcher.py"""; WorkingDir: "{app}\app"; IconFilename: "{app}\daytag.ico"; Comment: "{cm:About}"; Tasks: desktop

#ifndef Preview
[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "Daytag"; ValueData: """{app}\python\pythonw.exe"" ""{app}\app\launcher.py"" --start"; Flags: uninsdeletevalue; Tasks: autostart
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: none; ValueName: "Daytag"; Flags: deletevalue; Tasks: not autostart
#endif

[Run]
Filename: "{app}\python\pythonw.exe"; Parameters: """{app}\app\launcher.py"" --replace"; WorkingDir: "{app}\app"; Description: "{cm:OpenNow}"; Flags: nowait postinstall

[UninstallRun]
Filename: "{app}\python\pythonw.exe"; Parameters: """{app}\app\launcher.py"" --stop"; RunOnceId: "StopDaytag"

[UninstallDelete]
; Python writes compiled files next to its own and to ours.
Type: filesandordirs; Name: "{app}\python"
Type: filesandordirs; Name: "{app}\app\__pycache__"
Type: dirifempty; Name: "{app}\app"
Type: dirifempty; Name: "{app}"

[Code]
// There is no page in between, so the button that starts the installation says so.
procedure CurPageChanged(CurPageID: Integer);
begin
  if CurPageID = wpSelectTasks then
    WizardForm.NextButton.Caption := SetupMessage(msgButtonInstall);
end;

// An update: the Daytag that runs holds its files open, so it stops before they are replaced. When it cannot be stopped,
// nothing has been touched yet, and the installer says what to do.
function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  Code: Integer;
  Python, Launcher: String;
begin
  Result := '';
  Python := ExpandConstant('{app}\python\pythonw.exe');
  Launcher := ExpandConstant('{app}\app\launcher.py');
  if FileExists(Python) and FileExists(Launcher) then
    // Only that one code. A copy that is too damaged to run at all must be repairable by installing again.
    if Exec(Python, '"' + Launcher + '" --stop', '', SW_HIDE, ewWaitUntilTerminated, Code) and (Code = 3) then
      Result := CustomMessage('StillRunning');
end;

#ifndef Preview
// Whoever leaves for good, or gives the computer away, can take the private links along. Without a question (a silent
// removal) they stay.
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  Folder: String;
begin
  if (CurUninstallStep <> usPostUninstall) or UninstallSilent then
    exit;
  Folder := GetEnv('USERPROFILE') + '\.daytag';
  if DirExists(Folder) then
    if SuppressibleMsgBox(FmtMessage(CustomMessage('DeleteSettings'), [Folder]), mbConfirmation, MB_YESNO or MB_DEFBUTTON2, IDNO) = IDYES then
      DelTree(Folder, True, True, True);
end;
#endif
