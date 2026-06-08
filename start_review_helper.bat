@echo off
REM 雙擊本檔案：先同步最新程式碼，再啟動複習小幫手 GUI
cd /d "%~dp0"

echo === 同步最新程式碼（git pull）===
git pull
if errorlevel 1 (
    echo.
    echo [警告] git pull 失敗或有衝突，請檢查上面的訊息。
    echo 程式仍會嘗試啟動，但建議先處理好同步問題。
    pause
)

echo.
echo === 啟動複習小幫手 GUI ===
set PYTHONUTF8=1
.\env\Scripts\python.exe review_helper_gui.py

if errorlevel 1 (
    echo.
    echo [錯誤] 程式異常結束，請查看上面的錯誤訊息。
    pause
)
