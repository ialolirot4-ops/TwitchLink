Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "E:\TwitchLink-3.5.4-Complete"
WshShell.Run "cmd /c py TwitchLink.py", 0
Set WshShell = Nothing