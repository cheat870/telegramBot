@echo off
cd /d "D:\Bot\TelegramBot"
:loop
echo [%date% %time%] Starting HappyHub Telegram Bot... >> "D:\Bot\TelegramBot\bot_output.log"
"C:\Python314\python.exe" -u "my_bot.py" >> "D:\Bot\TelegramBot\bot_output.log" 2>&1
echo [%date% %time%] Bot exited with code %errorlevel%. Restarting in 3 seconds... >> "D:\Bot\TelegramBot\bot_output.log"
ping 127.0.0.1 -n 4 >nul
goto loop
