@echo off
REM Build a Windows executable for the WF Tracker using PyInstaller.
SETLOCAL
"%~dp0\.venv\Scripts\python.exe" -m PyInstaller --onefile --name wf_tracker --add-data "wf_tracker\templates;templates" --add-data "wf_tracker\sources;sources" --add-data "wf_tracker\cache;cache" --add-data "wf_tracker\output;output" wf_tracker\main.py
IF %ERRORLEVEL% NEQ 0 (
  echo Build failed.
  EXIT /B %ERRORLEVEL%
)
echo Build complete. Executable is in dist\wf_tracker.exe
ENDLOCAL
