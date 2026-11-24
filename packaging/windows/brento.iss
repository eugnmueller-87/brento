; The Windows installer: one file, for the person running it, without administrator rights.
; Built by packaging/build.py, which first puts Brento, its own Python and the GitHub program into the Stage folder.
; "Preview" makes a test build with its own name and folder that never touches an installed Brento.
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
  #define Name "Brento Preview"
  #define Id "{{6B0C7C0E-3B1E-4E0B-8C0B-7A51C7E6B9D2}"
  #define OutFile "Brento-Windows-Preview"
#else
  #define Name "Brento"
  #define Id "{{E2B7A7D4-0D5C-4F3C-9F55-5D7B3B4C1A90}"
  #define OutFile "Brento-Windows"
#endif

[Setup]
AppId={#Id}
AppName={#Name}
AppVersion={#AppVersion}
AppVerName={#Name} {#AppVersion}
AppPublisher=Brento
AppPublisherURL=https://github.com/eugnmueller-87/brento
AppSupportURL=https://github.com/eugnmueller-87/brento/issues
AppUpdatesURL=https://github.com/eugnmueller-87/brento/releases/latest
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
SetupIconFile=brento.ico
UninstallDisplayIcon={app}\brento.ico
UninstallDisplayName={#Name}
OutputDir={#Output}
OutputBaseFilename={#OutFile}
Compression=lzma2/max
SolidCompression=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "german"; MessagesFile: "compiler:Languages\German.isl"

[Messages]
english.WelcomeLabel1=Welcome to Brento
english.WelcomeLabel2=One screen that tells you what needs you today: your tasks, your board and your meetings.%n%nBrento brings everything it needs. It installs only for you, so Windows asks for no administrator password.%n%nWhen it is done, Brento opens and asks one question per page. You can skip every one of them.%n%nEverything stays on this computer, and Brento only reads: it never changes a note, a card or an appointment.
english.FinishedHeadingLabel=Brento is ready
english.FinishedLabelNoIcons=Click Finish. Brento opens and walks you through the rest.%n%nTo open it later, press the Windows key, type Brento and press Enter.
english.FinishedLabel=Click Finish. Brento opens and walks you through the rest.%n%nTo open it later, press the Windows key, type Brento and press Enter.
german.WelcomeLabel1=Willkommen bei Brento
german.WelcomeLabel2=Ein Bildschirm, der dir zeigt, was dich heute braucht: deine Aufgaben, dein Board und deine Termine.%n%nBrento bringt alles mit, was es braucht. Es wird nur für dich installiert, darum fragt Windows nicht nach einem Administrator-Kennwort.%n%nDanach öffnet sich Brento und stellt eine Frage pro Seite. Jede davon kannst du überspringen.%n%nAlles bleibt auf diesem Computer, und Brento liest nur: Es ändert nie eine Notiz, eine Karte oder einen Termin. Die Oberfläche von Brento ist auf Englisch.
german.FinishedHeadingLabel=Brento ist bereit
german.FinishedLabelNoIcons=Klicke auf Fertigstellen. Brento öffnet sich und führt dich durch den Rest.%n%nSpäter öffnen: Windows-Taste drücken, Brento tippen, Eingabetaste.
german.FinishedLabel=Klicke auf Fertigstellen. Brento öffnet sich und führt dich durch den Rest.%n%nSpäter öffnen: Windows-Taste drücken, Brento tippen, Eingabetaste.

[CustomMessages]
english.Autostart=Start Brento when I sign in to Windows
english.Desktop=Put Brento on the desktop
english.OpenNow=Open Brento now
english.About=Brento: what needs you today
german.Autostart=Brento bei der Anmeldung an Windows starten
german.Desktop=Brento auf den Desktop legen
german.OpenNow=Brento jetzt öffnen
german.About=Brento: was dich heute braucht

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
Type: files; Name: "{userstartup}\Brento server.lnk"
#endif

[Files]
Source: "{#Stage}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{userprograms}\{#Name}"; Filename: "{app}\python\pythonw.exe"; Parameters: """{app}\app\launcher.py"""; WorkingDir: "{app}\app"; IconFilename: "{app}\brento.ico"; Comment: "{cm:About}"
Name: "{userdesktop}\{#Name}"; Filename: "{app}\python\pythonw.exe"; Parameters: """{app}\app\launcher.py"""; WorkingDir: "{app}\app"; IconFilename: "{app}\brento.ico"; Comment: "{cm:About}"; Tasks: desktop

#ifndef Preview
[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "Brento"; ValueData: """{app}\python\pythonw.exe"" ""{app}\app\launcher.py"" --start"; Flags: uninsdeletevalue; Tasks: autostart
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: none; ValueName: "Brento"; Flags: deletevalue; Tasks: not autostart
#endif

[Run]
Filename: "{app}\python\pythonw.exe"; Parameters: """{app}\app\launcher.py"" --replace"; WorkingDir: "{app}\app"; Description: "{cm:OpenNow}"; Flags: nowait postinstall

[UninstallRun]
Filename: "{app}\python\pythonw.exe"; Parameters: """{app}\app\launcher.py"" --stop"; RunOnceId: "StopBrento"

[UninstallDelete]
Type: filesandordirs; Name: "{app}\app\__pycache__"
Type: dirifempty; Name: "{app}\app"
Type: dirifempty; Name: "{app}"

[Code]
// An update: the Brento that runs holds its files open, so it stops before they are replaced.
function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  Code: Integer;
  Python, Launcher: String;
begin
  Result := '';
  Python := ExpandConstant('{app}\python\pythonw.exe');
  Launcher := ExpandConstant('{app}\app\launcher.py');
  if FileExists(Python) and FileExists(Launcher) then
    Exec(Python, '"' + Launcher + '" --stop', '', SW_HIDE, ewWaitUntilTerminated, Code);
end;
