$env:JAVA_HOME='C:\Program Files\Microsoft\jdk-21.0.11.10-hotspot'
$env:PATH="$env:JAVA_HOME\bin;$env:PATH"
$env:PLAYWRIGHT_HEADLESS='false'
$env:HTTPS_PROXY='http://127.0.0.1:7890'
$env:HTTP_PROXY='http://127.0.0.1:7890'
Set-Location C:\Users\Hasee\.qclaw\workspace\get_jobs
& .\gradlew.bat runZhilianV2 --no-daemon 2>&1 | Tee-Object -FilePath logs\zhilian_v2_console.log
