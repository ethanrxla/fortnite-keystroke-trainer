param(
    [string]$ProjectPath = 'C:\Users\ethan\OneDrive\Documents\Fortnite\KeystrokeTrainer'
)

$ErrorActionPreference = 'Stop'
$key = Read-Host 'Enter ElevenLabs API key (input hidden)' -AsSecureString
$pointer = [IntPtr]::Zero
$originalDirectory = Get-Location
try {
    $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($key)
    $env:ELEVENLABS_API_KEY = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
    Set-Location -LiteralPath $ProjectPath
    python tools/gen_voice.py --cues-only --render-recommended
    if ($LASTEXITCODE -ne 0) { throw "Voice rendering failed with exit code $LASTEXITCODE" }
}
finally {
    Remove-Item Env:ELEVENLABS_API_KEY -ErrorAction SilentlyContinue
    if ($pointer -ne [IntPtr]::Zero) {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)
    }
    $key.Dispose()
    Set-Location -LiteralPath $originalDirectory
}
