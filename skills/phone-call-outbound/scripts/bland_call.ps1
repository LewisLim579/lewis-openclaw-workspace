param(
  [Parameter(Mandatory=$true)][string]$To,
  [Parameter(Mandatory=$true)][string]$Task,
  [string]$Voice = "maya",
  [string]$FirstSentence,
  [int]$MaxDuration = 5,
  [switch]$Record,
  [switch]$WaitForGreeting,
  [switch]$DryRun
)

$ErrorActionPreference = 'Stop'

function Get-SecretValue {
  param([string]$Name)
  if ($env:$Name) { return $env:$Name }
  return $null
}

$apiKey = Get-SecretValue -Name 'BLAND_API_KEY'
if (-not $apiKey) {
  throw 'BLAND_API_KEY is not set. Configure it before placing a call.'
}

$body = @{
  phone_number = $To
  task = $Task
  voice = $Voice
  max_duration = $MaxDuration
  record = [bool]$Record
  wait_for_greeting = [bool]$WaitForGreeting
}

if ($FirstSentence) {
  $body.first_sentence = $FirstSentence
}

if ($env:BLAND_WEBHOOK_URL) {
  $body.webhook = $env:BLAND_WEBHOOK_URL
}

if ($env:BLAND_DEFAULT_FROM) {
  $body.from = $env:BLAND_DEFAULT_FROM
}

$json = $body | ConvertTo-Json -Depth 5

if ($DryRun) {
  [pscustomobject]@{
    dryRun = $true
    endpoint = 'https://api.bland.ai/v1/calls'
    payload = ($json | ConvertFrom-Json)
  } | ConvertTo-Json -Depth 6
  exit 0
}

$headers = @{
  Authorization = $apiKey
  'Content-Type' = 'application/json'
}

$response = Invoke-RestMethod -Method Post -Uri 'https://api.bland.ai/v1/calls' -Headers $headers -Body $json
$response | ConvertTo-Json -Depth 8
