@echo off
setlocal
set "BASE_DIR=%~dp0"
set "MAVEN_VERSION=3.9.16"
set "BUNDLED_MVN=%BASE_DIR%.mvn\apache-maven-%MAVEN_VERSION%\bin\mvn.cmd"
set "MAVEN_ARCHIVE=%BASE_DIR%.mvn\apache-maven-%MAVEN_VERSION%-bin.zip"
set "MAVEN_ARCHIVE_TMP=%MAVEN_ARCHIVE%.tmp"
set "MAVEN_URL=https://archive.apache.org/dist/maven/maven-3/%MAVEN_VERSION%/binaries/apache-maven-%MAVEN_VERSION%-bin.zip"
set "MAVEN_SHA512=ed41650d42485cfc243fad22158caf9cbb5dc408ce7a09ddb94dd42a019de929ca43065bfa450612cf12bf78b5cafa3884b96c090de326ff590448c933454af3"

if exist "%BUNDLED_MVN%" goto run_bundled
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='Stop'; $archive=$env:MAVEN_ARCHIVE; $temp=$env:MAVEN_ARCHIVE_TMP; $expected=$env:MAVEN_SHA512; if (-not (Test-Path -LiteralPath $archive)) { Remove-Item -LiteralPath $temp -Force -ErrorAction SilentlyContinue; Invoke-WebRequest -UseBasicParsing -Uri $env:MAVEN_URL -OutFile $temp; $actual=(Get-FileHash -Algorithm SHA512 -LiteralPath $temp).Hash.ToLowerInvariant(); if ($actual -ne $expected) { Remove-Item -LiteralPath $temp -Force -ErrorAction SilentlyContinue; throw 'Maven distribution checksum verification failed' }; Move-Item -LiteralPath $temp -Destination $archive }; $actual=(Get-FileHash -Algorithm SHA512 -LiteralPath $archive).Hash.ToLowerInvariant(); if ($actual -ne $expected) { throw 'Maven distribution checksum verification failed' }; Expand-Archive -LiteralPath $archive -DestinationPath (Join-Path $env:BASE_DIR '.mvn') -Force"
if %ERRORLEVEL% NEQ 0 exit /b %ERRORLEVEL%
if not exist "%BUNDLED_MVN%" (
  echo Verified Maven distribution did not contain the expected executable.
  exit /b 127
)

:run_bundled
call "%BUNDLED_MVN%" %*
exit /b %ERRORLEVEL%
