#!/usr/bin/env bash
# Deploys/updates the Amplify -> Discord build notifier.
#
# Usage:
#   DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/..." ./deploy.sh
#
# Re-run any time you change lambda/index.js to push a code update.

set -euo pipefail

AMPLIFY_APP_ID="d2fpifryktvg3k"
REGION="ap-south-1"
FUNCTION_NAME="amplify-discord-notifier"
ROLE_NAME="amplify-discord-notifier-role"
RULE_NAME="amplify-discord-notifier-rule"

if [[ -z "${DISCORD_WEBHOOK_URL:-}" ]]; then
  echo "Set DISCORD_WEBHOOK_URL before running this script." >&2
  exit 1
fi

cd "$(dirname "$0")"

echo "Zipping function code..."
rm -f function.zip
(cd lambda && zip -q -r ../function.zip index.js)

ROLE_ARN=$(aws iam get-role --role-name "$ROLE_NAME" --query "Role.Arn" --output text 2>/dev/null || true)
if [[ -z "$ROLE_ARN" ]]; then
  echo "Creating IAM role $ROLE_NAME..."
  ROLE_ARN=$(aws iam create-role \
    --role-name "$ROLE_NAME" \
    --assume-role-policy-document '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"lambda.amazonaws.com"},"Action":"sts:AssumeRole"}]}' \
    --query "Role.Arn" --output text)
  aws iam attach-role-policy \
    --role-name "$ROLE_NAME" \
    --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
  echo "Waiting for role propagation..."
  sleep 10
fi

if aws lambda get-function --function-name "$FUNCTION_NAME" --region "$REGION" >/dev/null 2>&1; then
  echo "Updating existing Lambda function code + config..."
  aws lambda update-function-code \
    --function-name "$FUNCTION_NAME" --region "$REGION" \
    --zip-file fileb://function.zip >/dev/null
  aws lambda update-function-configuration \
    --function-name "$FUNCTION_NAME" --region "$REGION" \
    --environment "Variables={DISCORD_WEBHOOK_URL=$DISCORD_WEBHOOK_URL}" >/dev/null
else
  echo "Creating Lambda function..."
  aws lambda create-function \
    --function-name "$FUNCTION_NAME" --region "$REGION" \
    --runtime nodejs20.x \
    --role "$ROLE_ARN" \
    --handler index.handler \
    --zip-file fileb://function.zip \
    --timeout 10 \
    --environment "Variables={DISCORD_WEBHOOK_URL=$DISCORD_WEBHOOK_URL}" >/dev/null

  FUNCTION_ARN=$(aws lambda get-function --function-name "$FUNCTION_NAME" --region "$REGION" --query "Configuration.FunctionArn" --output text)

  echo "Creating EventBridge rule..."
  aws events put-rule \
    --name "$RULE_NAME" --region "$REGION" \
    --event-pattern "{\"source\":[\"aws.amplify\"],\"detail-type\":[\"Amplify Deployment Status Change\"],\"detail\":{\"appId\":[\"$AMPLIFY_APP_ID\"],\"jobStatus\":[\"SUCCEED\",\"FAILED\",\"STARTED\"]}}" \
    --state ENABLED >/dev/null

  aws events put-targets \
    --rule "$RULE_NAME" --region "$REGION" \
    --targets "[{\"Id\":\"1\",\"Arn\":\"$FUNCTION_ARN\"}]" >/dev/null

  aws lambda add-permission \
    --function-name "$FUNCTION_NAME" --region "$REGION" \
    --statement-id allow-eventbridge \
    --action lambda:InvokeFunction \
    --principal events.amazonaws.com \
    --source-arn "arn:aws:events:$REGION:$(aws sts get-caller-identity --query Account --output text):rule/$RULE_NAME" >/dev/null
fi

rm -f function.zip
echo "Done."
