# Provider notes

## Bland AI

- Endpoint: `POST https://api.bland.ai/v1/calls`
- Minimum useful inputs: `phone_number`, `task`
- Helpful optional inputs: `first_sentence`, `voice`, `max_duration`, `record`, `wait_for_greeting`
- Best for: short outbound utility calls, test calls, scripted requests

## Recommended rollout

1. Dry run locally first.
2. Place a test call to the user's own number.
3. Only then place calls to third parties.
4. Keep explicit approval in chat for every live call.

## Secrets to configure

Set these in the environment or a secure secret store:

- `BLAND_API_KEY` required
- `BLAND_DEFAULT_FROM` optional
- `BLAND_WEBHOOK_URL` optional

## Example dry run

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\bland_call.ps1 -To "+821012345678" -Task "현우님께 테스트 전화" -FirstSentence "안녕하세요, 얄리입니다." -DryRun
```
