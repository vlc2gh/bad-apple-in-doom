@echo off
rem Opens DOSBox at C:\ = release\ ; type DOOM to start.
rem Set DOSBOX to your DOSBox.exe if it is not in the default install folder.
if not defined DOSBOX set "DOSBOX=C:\Program Files (x86)\DOSBox-0.74-3\DOSBox.exe"
cd /d "%~dp0release"
"%DOSBOX%" -conf "%~dp0dosbox-shell.conf" -noconsole
