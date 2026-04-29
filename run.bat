@echo off
echo ============================================
echo   Awaaz — Smart Grievance Redressal System
echo ============================================
echo.

:: Create .env if it doesn't exist
if not exist backend\.env (
    copy .env.example backend\.env >nul
    echo Created backend\.env from template.
    echo Edit backend\.env to add your GEMINI_API_KEY if available.
    echo.
)

:: Install dependencies
echo Installing Python dependencies...
pip install -r backend\requirements.txt --quiet

echo.
echo Starting server at http://localhost:5000
echo Press Ctrl+C to stop.
echo.
cd backend
python app.py
