# Synthetic test recording (Windows SAPI voice): fixture script 1 read with a flubbed first take and a retake.
param([string]$Out = "$PSScriptRoot\_test-voice.wav")
Add-Type -AssemblyName System.Speech
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
$s.Rate = 1
$p = '<break time="900ms"/>'
$lines = @(
  "Last year storms left over two million homes in the... uh, sorry, let me start again.",
  "Last year storms left over two million homes in the dark.",
  "I'm Alex.",
  "The test is on the seventeenth.",
  "If the power goes out, call nine one one only for emergencies.",
  "Keep your fridge closed: food stays cold for... no wait.",
  "Keep your fridge closed: food stays cold for four hours.",
  "Comment BACKUP and I'll send you the link."
)
$ssml = '<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="en-US">' + (($lines | ForEach-Object { [System.Security.SecurityElement]::Escape($_) }) -join $p) + '</speak>'
$s.SetOutputToWaveFile($Out)
$s.SpeakSsml($ssml)
$s.Dispose()
Write-Output "Wrote $Out"
