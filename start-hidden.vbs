' Runs restart.cmd without a console window. Called by the scheduled task "Daytag".
Set shell = CreateObject("WScript.Shell")
here = Left(WScript.ScriptFullName, InStrRev(WScript.ScriptFullName, "\"))
shell.Run "cmd /c """ & here & "restart.cmd""", 0, False
