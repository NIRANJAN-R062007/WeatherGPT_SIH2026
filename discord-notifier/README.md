# Amplify → Discord build notifier

Posts a Discord message whenever an Amplify build for `WeatherGPT_SIH2026`
(app id `d2fpifryktvg3k`, region `ap-south-1`) starts, succeeds, or fails.

## How it works

```
Amplify build status change
        │
        ▼
EventBridge rule (amplify-discord-notifier-rule)
        │
        ▼
Lambda (amplify-discord-notifier)  ──POST──▶  Discord webhook
```

No bot process, no server to keep running — pure event-driven.

## Files

- `lambda/index.js` — Lambda handler. Formats the Amplify EventBridge event
  and posts an embed to the Discord webhook URL in `DISCORD_WEBHOOK_URL`.
- `deploy.sh` — creates/updates the IAM role, Lambda function, EventBridge
  rule, and permissions. Idempotent — safe to re-run after editing `index.js`.

## Deploying / redeploying

```bash
DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/..." ./deploy.sh
```

Never commit the webhook URL — pass it as an env var only.

## Changing which statuses notify

Edit the `jobStatus` list in `deploy.sh`'s event pattern (currently
`SUCCEED`, `FAILED`, `STARTED`) and re-run the script.

## Testing without a real build

```bash
aws lambda invoke \
  --function-name amplify-discord-notifier --region ap-south-1 \
  --payload '{"detail":{"appId":"d2fpifryktvg3k","branchName":"main","jobId":"1","jobStatus":"SUCCEED"}}' \
  --cli-binary-format raw-in-base64-out \
  /tmp/response.json && cat /tmp/response.json
```
