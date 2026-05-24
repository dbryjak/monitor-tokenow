Dim oShell
Set oShell = CreateObject("WScript.Shell")
oShell.Environment("Process")("PYTHONUTF8") = "1"
oShell.Run "C:\Python314\pythonw.exe ""D:\MOJE PROJEKTY\Monitor-Tokenow\tray_monitor.py""", 0, False
Set oShell = Nothing
