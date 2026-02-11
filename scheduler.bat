@echo off
chcp 65001 > nul 2>&1

if "%~7"=="" goto usage

set INTERVAL=%~1
set ARGS=%~2 %~3 %~4 %~5 %~6 %~7 %~8

set ATTEMPT=0

:loop
set /a ATTEMPT+=1
echo.
echo ===== Attempt %ATTEMPT% =====
python main.py %ARGS%
if %ERRORLEVEL%==0 goto success
if %ERRORLEVEL%==2 goto no_seats
goto error

:no_seats
echo No seats, retry in %INTERVAL% seconds...
timeout /t %INTERVAL% /nobreak > nul 2>&1
goto loop

:success
echo Booking success!
exit /b 0

:error
echo Error, stopping scheduler.
exit /b 1

:usage
echo Usage: scheduler.bat [interval_seconds] [account] [from] [to] [date] [train_no] [seat_pref] [target_car]
exit /b 1
