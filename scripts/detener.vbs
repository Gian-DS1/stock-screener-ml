' Sniper Screener - Detener
' Cierra el backend local. No afecta tus datos (todo queda guardado en disco).
Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
base = fso.GetParentFolderName(WScript.ScriptFullName)
q = Chr(34)

sh.Run "cmd /c " & q & base & "\_stop_server.bat" & q, 0, True
MsgBox "Sniper Screener detenido." & vbCrLf & "Tus datos y señales quedaron guardados.", 64, "Sniper Screener"
