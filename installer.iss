[Setup]
AppName=TrackIt
AppVersion=1.0
DefaultDirName={pf}\TrackIt
DefaultGroupName=TrackIt
OutputDir=Output
OutputBaseFilename=TrackIt_Installer
Compression=lzma
SolidCompression=yes
PrivilegesRequired=admin

[Files]
Source: "dist\TrackIt.exe"; DestDir: "{app}"; Flags: ignoreversion

[Tasks]
Name: "startup"; Description: "Run TrackIt at Windows startup"

[Run]
Filename: "powershell.exe"; \
Parameters: "-NoProfile -ExecutionPolicy Bypass -Command ""$action = New-ScheduledTaskAction -Execute '""{app}\TrackIt.exe""'; $trigger = New-ScheduledTaskTrigger -AtStartup; Register-ScheduledTask -TaskName 'TrackIt' -Action $action -Trigger $trigger -Description 'Runs TrackIt at startup' -RunLevel Highest -Force"""; \
Flags: runhidden; Tasks: startup

[UninstallDelete]
Type: filesandordirs; Name: "{app}"

[UninstallRun]
Filename: "powershell.exe"; \
Parameters: "-NoProfile -ExecutionPolicy Bypass -Command ""Unregister-ScheduledTask -TaskName 'TrackIt' -Confirm:$false"""; \
Flags: runhidden