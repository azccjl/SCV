$ErrorActionPreference = 'Stop'
$port = 8501
$health = Invoke-WebRequest "http://127.0.0.1:$port/_stcore/health" -UseBasicParsing -TimeoutSec 5
if ($health.StatusCode -ne 200) { throw "Streamlit health check failed" }
Write-Output "Streamlit is healthy at http://127.0.0.1:$port"
