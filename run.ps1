# Run Breathe ESG locally (backend + built frontend on one port)
$ErrorActionPreference = "Stop"
$root = $PSScriptRoot

Write-Host "Installing backend dependencies..."
pip install -r "$root\backend\requirements.txt" -q

Write-Host "Building frontend..."
Set-Location "$root\frontend"
npm install --silent
npm run build
Set-Location $root

Write-Host "Database setup..."
Set-Location "$root\backend"
python manage.py migrate
python manage.py seed_demo

Write-Host ""
Write-Host "Starting server at http://127.0.0.1:8000"
Write-Host "Login: analyst / demo1234"
Write-Host ""
python manage.py runserver 8000
