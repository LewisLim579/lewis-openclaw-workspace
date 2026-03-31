<#
.SYNOPSIS
    Windows SAPI5 TTS - Lightweight text-to-speech
.DESCRIPTION
    Uses Windows built-in speech synthesis (SAPI5).
    Works with Neural voices (Win11) or legacy voices (Win10).
    Zero GPU usage, instant generation.
#>

param(
    [Parameter(Mandatory=$false, Position=0)]
    [string]$Text = "",
    
    [Parameter(Mandatory=$false)]
    [Alias("Voice", "v")]
    [string]$VoiceName = "",
    
    [Parameter(Mandatory=$false)]
    [Alias("Lang", "l")]
    [string]$Language = "ko",
    
    [Parameter(Mandatory=$false)]
    [Alias("o")]
    [string]$Output = "",
    
    [Parameter(Mandatory=$false)]
    [Alias("r")]
    [int]$Rate = 0,
    
    [Parameter(Mandatory=$false)]
    [Alias("p")]
    [switch]$Play,
    
    [Parameter(Mandatory=$false)]
    [switch]$ListVoices
)

Add-Type -AssemblyName System.Speech
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer

$installedVoices = $synth.GetInstalledVoices() | Where-Object { $_.Enabled } | ForEach-Object { $_.VoiceInfo }

if ($ListVoices) {
    Write-Host "`nInstalled SAPI5 voices:`n" -ForegroundColor Cyan
    foreach ($v in $installedVoices) {
        $type = if ($v.Name -match "Online|Neural") { "[Neural]" } else { "[Legacy]" }
        Write-Host "  $($v.Name)" -ForegroundColor White -NoNewline
        Write-Host " $type" -ForegroundColor DarkGray -NoNewline
        Write-Host " - $($v.Culture) $($v.Gender)" -ForegroundColor Gray
    }
    Write-Host ""
    $synth.Dispose()
    exit 0
}

if (-not $Text) {
    Write-Error "Text required. Use: .\tts.ps1 'Your text here'"
    Write-Host "Use -ListVoices to see available voices"
    $synth.Dispose()
    exit 1
}

function Select-BestVoice {
    param($voices, $preferredName, $lang)
    
    if ($preferredName) {
        $match = $voices | Where-Object { $_.Name -like "*$preferredName*" } | Select-Object -First 1
        if ($match) { return $match }
        Write-Warning "Voice '$preferredName' not found, auto-selecting..."
    }
    
    $cultureMap = @{
        "ko" = "ko-KR"; "korean" = "ko-KR"
        "en" = "en-US"; "english" = "en-US"
        "ja" = "ja-JP"; "japanese" = "ja-JP"
        "zh" = "zh-CN"; "chinese" = "zh-CN"
        "fr" = "fr-FR"; "french" = "fr-FR"
        "de" = "de-DE"; "german" = "de-DE"
        "es" = "es-ES"; "spanish" = "es-ES"
        "it" = "it-IT"; "italian" = "it-IT"
    }
    $targetCulture = $cultureMap[$lang.ToLower()]
    if (-not $targetCulture) { $targetCulture = $lang }
    
    $neuralMatch = $voices | Where-Object { 
        $_.Name -match "Online|Neural" -and $_.Culture.Name -eq $targetCulture 
    } | Select-Object -First 1
    if ($neuralMatch) { return $neuralMatch }
    
    $langMatch = $voices | Where-Object { $_.Culture.Name -eq $targetCulture } | Select-Object -First 1
    if ($langMatch) { return $langMatch }
    
    $anyNeural = $voices | Where-Object { $_.Name -match "Online|Neural" } | Select-Object -First 1
    if ($anyNeural) { return $anyNeural }
    
    return $voices | Select-Object -First 1
}

$selectedVoice = Select-BestVoice -voices $installedVoices -preferredName $VoiceName -lang $Language

if (-not $selectedVoice) {
    Write-Error "No SAPI5 voices found! Install voices in Windows Settings > Time & Language > Speech"
    $synth.Dispose()
    exit 1
}

if (-not $Output) {
    $ttsDir = "$env:USERPROFILE\.openclaw\workspace\tts"
    if (-not (Test-Path $ttsDir)) { New-Item -ItemType Directory -Path $ttsDir -Force | Out-Null }
    $timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $Output = "$ttsDir\sapi_$timestamp.wav"
}

try {
    $synth.SelectVoice($selectedVoice.Name)
    $synth.Rate = $Rate
    $synth.SetOutputToWaveFile($Output)
    $synth.Speak($Text)
    $synth.SetOutputToNull()
    
    Write-Host "Voice: $($selectedVoice.Name) [$($selectedVoice.Culture)]" -ForegroundColor Cyan
    Write-Host "MEDIA:$Output"
    
    if ($Play) {
        Add-Type -AssemblyName PresentationCore
        $player = New-Object System.Windows.Media.MediaPlayer
        $player.Open([Uri]$Output)
        $player.Play()
        Start-Sleep -Milliseconds 500
        while ($player.NaturalDuration.HasTimeSpan -and $player.Position -lt $player.NaturalDuration.TimeSpan) {
            Start-Sleep -Milliseconds 100
        }
        $player.Close()
    }
    
} catch {
    Write-Error "TTS failed: $($_.Exception.Message)"
    exit 1
} finally {
    $synth.Dispose()
}
