# Randis UDS™ by Randy Moore. Original: https://github.com/RandyWilliamMoore/randis-uds · Support: https://ko-fi.com/moorescombinatoricsmatrix
$ErrorActionPreference = "Continue"
$venv = Join-Path $env:USERPROFILE "voice_lab_tts_venv_gpu"
$cpu = Join-Path $env:USERPROFILE "voice_lab_tts_venv"
$log = Join-Path $env:USERPROFILE "voice_lab_tts_venv_gpu_setup.log"
Start-Transcript -Path $log -Append | Out-Null
Write-Host "Randis UDS: setting up the graphics-card voice engine in $venv" -ForegroundColor Cyan
$py = "C:\Python314\python.exe"
if (-not (Test-Path "$venv\Scripts\python.exe")) { & $py -m venv $venv }
$vp = "$venv\Scripts\python.exe"
& $vp -m pip install --upgrade pip --retries 10 --timeout 120
Write-Host "Step 1 of 3: PyTorch for NVIDIA cards (CUDA 12.6, about 2.5 GB)..." -ForegroundColor Cyan
for ($i = 1; $i -le 5; $i++) {
  & $vp -m pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu126 --retries 10 --timeout 180
  if ($LASTEXITCODE -eq 0) { break }; Write-Host "Download interrupted; trying again ($i of 5)..." -ForegroundColor Yellow; Start-Sleep 5
}
Write-Host "Step 2 of 3: the voice engine's other parts (same versions as the working engine)..." -ForegroundColor Cyan
$req = Join-Path $PSScriptRoot "voice_gpu_requirements.txt"
for ($i = 1; $i -le 5; $i++) {
  & $vp -m pip install --no-deps -r $req --retries 10 --timeout 180
  if ($LASTEXITCODE -eq 0) { break }; Write-Host "Trying again ($i of 5)..." -ForegroundColor Yellow; Start-Sleep 5
}
Copy-Item "$cpu\Lib\site-packages\sitecustomize.py" "$venv\Lib\site-packages\sitecustomize.py" -Force
Write-Host "Step 3 of 3: checking..." -ForegroundColor Cyan
& $vp -c "import torch, chatterbox; print('PyTorch', torch.__version__, '| CUDA build', torch.version.cuda, '| card usable now:', torch.cuda.is_available())"
if ($LASTEXITCODE -eq 0) { Write-Host "DONE. The graphics-card engine is installed." -ForegroundColor Green
  Write-Host "If 'card usable now' says False, update the NVIDIA driver (nvidia.com > Drivers > GeForce RTX 2060), restart the PC, then switch it on in the Voice library page." -ForegroundColor Green }
else { Write-Host "Something didn't install. Run this again, or ask Claude in the app's chat (the log is $log)." -ForegroundColor Red }
Stop-Transcript | Out-Null
