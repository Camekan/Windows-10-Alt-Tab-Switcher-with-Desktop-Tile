' start_alttab.vbs - launches desktop_alttab.py with no console window.
'
' 1. Replace the path below with where YOU saved desktop_alttab.py
'    (keep the double quote marks around it).
' 2. Copy this file into your Startup folder (Win+R, type shell:startup).

Set WShell = CreateObject("WScript.Shell")
WShell.Run "pythonw.exe ""C:\Users\YourName\Downloads\desktop_alttab.py""", 0, False
Set WShell = Nothing
