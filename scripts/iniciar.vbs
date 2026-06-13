' Stock Screener - Lanzador
' Arranca el backend local (sin ventana visible) y abre el dashboard en el navegador.
' El servidor escucha solo en 127.0.0.1 => invisible para la red y para internet.
Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
base = fso.GetParentFolderName(WScript.ScriptFullName)
q = Chr(34)

' Lanza el servidor en una ventana oculta (0 = sin ventana)
sh.Run "cmd /c " & q & base & "\_run_server.bat" & q, 0, False

' Da tiempo a que el backend levante (uv + carga del modelo) y abre el dashboard
WScript.Sleep 9000
sh.Run "http://localhost:8000/", 1, False
