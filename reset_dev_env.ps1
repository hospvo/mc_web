# reset_dev_env.ps1
Write-Host "Removing existing migrations and database..."
Remove-Item -Recurse -Force .\migrations\
Remove-Item .\instance\db.sqlite3

Write-Host "Reinitializing migrations..."
flask db init
flask db migrate -m "Initial"
flask db upgrade

Write-Host "Done. Database and migrations are fresh."