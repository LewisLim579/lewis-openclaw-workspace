---
name: phone-call-outbound
description: Place outbound phone calls through a connected provider such as Bland AI. Use when the user wants the agent to call someone, trigger a test call to the user, read a short scripted message, or create a reusable outbound-calling setup that requires explicit approval before any live call.
---

# Phone Call Outbound

Place outbound calls through a provider-backed script. Treat live calls as external actions that always require explicit user approval.

## Workflow

1. Confirm the target number, purpose, and whether this is a real call or a test.
2. Confirm the provider is configured. This skill ships with a Bland AI script and can be adapted to other providers later.
3. Show the exact command or payload before placing a live call.
4. After approval, run the script and report the returned call id or failure.
5. If needed, poll for completion and summarize the result.

## Current bundled provider

Use the bundled script in `scripts/bland_call.ps1` for Windows/PowerShell environments.

Required secret:
- `BLAND_API_KEY`

Optional environment values:
- `BLAND_DEFAULT_FROM`
- `BLAND_WEBHOOK_URL`

## Safe operating rules

- Never place a live call without explicit approval in the current conversation.
- Prefer a short scripted first sentence for test calls.
- Keep numbers in E.164 format when possible, for example `+821012345678`.
- If the user only wants setup, validate configuration with `--dry-run` and do not call the API.

## Common uses

### Test call to the user

Use a simple prompt such as:
- "현우님께 테스트 전화를 겁니다. 받으시면 얄리 테스트라고 말씀드려 주세요."

### Ask someone to do something

Use a concise task with fallback behavior:
- identify who is calling on whose behalf
- state the request clearly
- keep it under 20-30 seconds if possible

## Commands

Dry run:

```powershell
./scripts/bland_call.ps1 -To "+8210..." -Task "테스트 전화" -FirstSentence "안녕하세요, 얄리입니다." -DryRun
```

Live call:

```powershell
./scripts/bland_call.ps1 -To "+8210..." -Task "현우님께 테스트 전화" -FirstSentence "안녕하세요, 얄리입니다. 테스트 전화예요."
```

## Troubleshooting

- If the API key is missing, set `BLAND_API_KEY` in the environment before running.
- If the provider rejects the number, verify E.164 formatting and country support.
- If live calling is not desired, use this skill only for setup and dry-run validation.
