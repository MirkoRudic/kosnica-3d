' Kosnica 3D: pokrece lokalnu app bez prozora konzole i drzi precicu na Desktopu.
' Prvo pokretanje (nema .venv) ide preko instaliraj.bat.
Option Explicit
Dim fso, ljuska, mapa, pyw, precica, ikona
Set fso = CreateObject("Scripting.FileSystemObject")
Set ljuska = CreateObject("WScript.Shell")
mapa = fso.GetParentFolderName(WScript.ScriptFullName)
pyw = mapa & "\.venv\Scripts\pythonw.exe"
ikona = mapa & "\kosnica.ico"
ljuska.CurrentDirectory = mapa

On Error Resume Next
Set precica = ljuska.CreateShortcut(ljuska.SpecialFolders("Desktop") & "\Ko" & ChrW(353) & "nica 3D.lnk")
precica.TargetPath = WScript.ScriptFullName
precica.WorkingDirectory = mapa
precica.Description = "Ko" & ChrW(353) & "nica 3D"
If fso.FileExists(ikona) Then precica.IconLocation = ikona & ", 0"
precica.Save
Err.Clear
On Error GoTo 0

If fso.FileExists(pyw) Then
    ljuska.Run """" & pyw & """ """ & mapa & "\kosnica3d.pyw""", 0, False
Else
    ljuska.Run """" & mapa & "\instaliraj.bat""", 1, False
End If
