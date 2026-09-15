# Start Acme Approvals in the background on http://localhost:8090 (Windows)
Set-Location $PSScriptRoot
python -m pip install -q -r requirements.txt
Start-Process -WindowStyle Hidden python -ArgumentList "app.py"
Write-Host "Acme Approvals running at http://localhost:8090/"
