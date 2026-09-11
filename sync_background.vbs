Option Explicit
Dim shell, fso, root, pythonw, agent
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
root = fso.GetParentFolderName(WScript.ScriptFullName)
pythonw = root & "\.venv\Scripts\pythonw.exe"
agent = root & "\sync_agent.py"
If fso.FileExists(pythonw) And fso.FileExists(agent) Then
  shell.Run Chr(34) & pythonw & Chr(34) & " " & Chr(34) & agent & Chr(34), 0, False
End If
