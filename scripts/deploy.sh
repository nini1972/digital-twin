#!/bin/bash
set -e

ENVIRONMENT=${1:-dev}          # dev | test | prod
PROJECT_NAME=${2:-twin}

echo "🚀 Deploying ${PROJECT_NAME} to ${ENVIRONMENT}..."

# 1. Build Lambda package
cd "$(dirname "$0")/.."        # project root
echo "📦 Building Lambda package..."
(cd backend && uv run deploy.py)

# Guard: OPENAI_API_KEY is required for the Lambda chat endpoint.
# Fail fast here rather than deploying a broken Lambda silently.
if [ -z "${OPENAI_API_KEY:-}" ]; then
  echo "❌ Error: OPENAI_API_KEY is not set." >&2
  echo "   Set it as a GitHub Actions environment secret (dev/test/prod)" >&2
  echo "   or export it in your shell before running this script." >&2
  exit 1
fi

# Store the API key in Secrets Manager so the raw value never touches
# Terraform state. The secret is created here (before terraform runs) and
# Terraform only receives the ARN for the IAM policy and Lambda env var.
OPENAI_SECRET_NAME="${PROJECT_NAME}-${ENVIRONMENT}-openai-api-key"
echo "🔑 Writing OpenAI API key to Secrets Manager (${OPENAI_SECRET_NAME})..."
DESCRIBE_OUTPUT=$(aws secretsmanager describe-secret --secret-id "$OPENAI_SECRET_NAME" 2>&1 >/dev/null) && SECRET_EXISTS=true || SECRET_EXISTS=false

if [ "$SECRET_EXISTS" = "true" ]; then
  aws secretsmanager put-secret-value \
    --secret-id "$OPENAI_SECRET_NAME" \
    --secret-string "$OPENAI_API_KEY"
elif echo "$DESCRIBE_OUTPUT" | grep -q "ResourceNotFoundException"; then
  aws secretsmanager create-secret \
    --name "$OPENAI_SECRET_NAME" \
    --description "OpenAI API key for ${PROJECT_NAME} ${ENVIRONMENT} Lambda" \
    --secret-string "$OPENAI_API_KEY"
else
  echo "❌ Error accessing Secrets Manager for '${OPENAI_SECRET_NAME}':" >&2
  echo "   ${DESCRIBE_OUTPUT}" >&2
  echo "   Ensure the deploy role has secretsmanager:DescribeSecret, secretsmanager:CreateSecret," >&2
  echo "   secretsmanager:PutSecretValue, and secretsmanager:GetSecretValue on 'arn:aws:secretsmanager:*:*:secret:${OPENAI_SECRET_NAME}*'." >&2
  echo "   See iam/github-actions-deploy-policy.json for the full required policy." >&2
  exit 1
fi

# 2. Terraform workspace & apply
cd terraform
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
AWS_REGION=${DEFAULT_AWS_REGION:-us-east-1}
terraform init -input=false \
  -backend-config="bucket=twin-terraform-state-${AWS_ACCOUNT_ID}" \
  -backend-config="key=${ENVIRONMENT}/terraform.tfstate" \
  -backend-config="region=${AWS_REGION}" \
  -backend-config="dynamodb_table=twin-terraform-locks" \
  -backend-config="encrypt=true"

if ! terraform workspace list | grep -q "$ENVIRONMENT"; then
  terraform workspace new "$ENVIRONMENT"
else
  terraform workspace select "$ENVIRONMENT"
fi

# Use prod.tfvars for production environment
if [ "$ENVIRONMENT" = "prod" ]; then
  TF_APPLY_CMD=(terraform apply -var-file=prod.tfvars -var="project_name=$PROJECT_NAME" -var="environment=$ENVIRONMENT" -auto-approve)
else
  TF_APPLY_CMD=(terraform apply -var="project_name=$PROJECT_NAME" -var="environment=$ENVIRONMENT" -auto-approve)
fi

echo "🎯 Applying Terraform..."
"${TF_APPLY_CMD[@]}"

API_URL=$(terraform output -raw api_gateway_url)
FRONTEND_BUCKET=$(terraform output -raw s3_frontend_bucket)
CUSTOM_URL=$(terraform output -raw custom_domain_url 2>/dev/null || true)

# 3. Build + deploy frontend
cd ../frontend

# Create production environment file with API URL
echo "📝 Setting API URL for production..."
echo "NEXT_PUBLIC_API_URL=$API_URL" > .env.production

npm install
npm run build
aws s3 sync ./out "s3://$FRONTEND_BUCKET/" --delete
cd ..

# 4. Final messages
echo -e "\n✅ Deployment complete!"
echo "🌐 CloudFront URL : $(terraform -chdir=terraform output -raw cloudfront_url)"
if [ -n "$CUSTOM_URL" ]; then
  echo "🔗 Custom domain  : $CUSTOM_URL"
fi
echo "📡 API Gateway    : $API_URL"