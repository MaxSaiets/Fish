' Прихований запуск запланованої задачі fish-sync БЕЗ видимого вікна.
' Task Scheduler викликає: wscript.exe //Nologo run_hidden.vbs "src\notify_new_orders.py"
' WScript.Shell.Run(..., 0, True): 0 = вікно приховане, True = чекати завершення
' (щоб задача коректно відображала результат і діяв ExecutionTimeLimit).
Option Explicit
Dim sh, fso, root, script, cmd
Set sh = CreateObject("WScript.Shell")
' Корінь проєкту = батьківська тека для docs\, де лежить цей файл.
' Хардкод шляху прибрано 04.08.2026: він змушував правити файл локально на
' машинах з іншим шляхом, а локальні правки блокують git pull.
Set fso = CreateObject("Scripting.FileSystemObject")
root = fso.GetParentFolderName(fso.GetParentFolderName(WScript.ScriptFullName))
If WScript.Arguments.Count > 0 Then
    script = WScript.Arguments(0)
Else
    script = "src\notify_new_orders.py"
End If
cmd = "powershell.exe -ExecutionPolicy Bypass -NonInteractive -File """ & root & "\docs\run_task.ps1"" -Script """ & script & """"
sh.Run cmd, 0, True
