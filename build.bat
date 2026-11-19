@echo off
rem Full build: badapple.mp4 + DOOM.EXE/DOOM.WAD v1.9 -> BADAPPLE.WAD, BADAPPLE.EXE, release\
cd /d "%~dp0"
python tools\extract_media.py || exit /b 1
python tools\make_menu_gfx.py || exit /b 1
python tools\build_wad.py || exit /b 1
python tools\patch_exe.py || exit /b 1
python tools\make_release.py || exit /b 1
