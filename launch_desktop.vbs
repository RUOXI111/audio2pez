Option Explicit
Dim shell, files, baseDir, pythonPath, appPath, command
Set shell = CreateObject("WScript.Shell")
Set files = CreateObject("Scripting.FileSystemObject")
baseDir = files.GetParentFolderName(WScript.ScriptFullName)
pythonPath = files.BuildPath(baseDir, ".venv\Scripts\pythonw.exe")
appPath = files.BuildPath(baseDir, "desktop_app.py")
If Not files.FileExists(pythonPath) Or Not files.FileExists(appPath) Then
  MsgBox "Desktop files or local Python are missing. Use launch_desktop.cmd for diagnostics.", 16, "Audio2Phira"
  WScript.Quit 1
End If
shell.CurrentDirectory = baseDir
command = Chr(34) & pythonPath & Chr(34) & " -X utf8 " & Chr(34) & appPath & Chr(34)
On Error Resume Next
shell.Run command, 0, False
If Err.Number <> 0 Then
  MsgBox "Unable to start Audio2Phira: " & Err.Description & vbCrLf & "Use launch_desktop.cmd for diagnostics.", 16, "Audio2Phira"
  WScript.Quit 1
End If
