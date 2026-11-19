@echo off
rem Dev run: original DOOM.EXE layout with BADAPPLE.EXE + BADAPPLE.WAD as a PWAD.
rem Set DOSBOX to your DOSBox.exe if it is not in the default install folder.
cd /d "%~dp0"
if not defined DOSBOX set "DOSBOX=C:\Program Files (x86)\DOSBox-0.74-3\DOSBox.exe"
"%DOSBOX%" -conf dosbox-badapple.conf -noconsole
