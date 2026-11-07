Option Explicit
Dim shell, files, baseDir, guiPath, powershellPath, command
Set shell = CreateObject("WScript.Shell")
Set files = CreateObject("Scripting.FileSystemObject")
baseDir = files.GetParentFolderName(WScript.ScriptFullName)
guiPath = files.BuildPath(baseDir, "installer_gui.ps1")
powershellPath = shell.ExpandEnvironmentStrings("%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe")
If Not files.FileExists(guiPath) Then
  MsgBox "Installer files are missing. Extract the complete Audio2Phira package, including installer_gui.ps1, and try again.", 16, "Audio2Phira Setup"
  WScript.Quit 1
End If
If Not files.FileExists(powershellPath) Then
  MsgBox "Windows PowerShell 5.1 is missing. Enable Windows PowerShell and try again.", 16, "Audio2Phira Setup"
  WScript.Quit 1
End If
shell.CurrentDirectory = baseDir
command = Chr(34) & powershellPath & Chr(34) & " -NoProfile -ExecutionPolicy Bypass -STA -WindowStyle Hidden -File " & Chr(34) & guiPath & Chr(34)
On Error Resume Next
shell.Run command, 0, False
If Err.Number <> 0 Then
  MsgBox "Unable to start Audio2Phira Setup: " & Err.Description & vbCrLf & "Open Setup.cmd to see diagnostics.", 16, "Audio2Phira Setup"
  WScript.Quit 1
End If
