<#
.SYNOPSIS
    One-time IAM setup for GitHub Actions OIDC-based deployments.

.DESCRIPTION
    Creates (or verifies) all IAM resources required so GitHub Actions can
    assume an IAM role via OIDC instead of storing long-lived AWS credentials:

        1. GitHub OIDC identity provider  (once per AWS account)
        2. IAM role with a trust policy   (trusts the configured repo + environments)
        3. Managed IAM policy             (from iam/github-actions-deploy-policy.json)
        4. Policy attachment              (attaches the policy to the role)

    The script is idempotent: resources that already exist are skipped with a
    notice rather than causing an error.

.PARAMETER GitHubOrg
    GitHub organization or user that owns the repository (e.g. "myorg").

.PARAMETER GitHubRepo
    Repository name (e.g. "digital-twin").

.PARAMETER RoleName
    Name of the IAM role to create. Defaults to "github-actions-deploy".

.PARAMETER PolicyName
    Name of the managed IAM policy to create. Defaults to "github-actions-deploy-policy".

.PARAMETER ProjectName
    Project prefix used in resource names. Defaults to "twin".

.PARAMETER Environments
    GitHub environments the role should be allowed to assume from.
    Defaults to @("dev","test","prod").

.EXAMPLE
    .\scripts\setup-iam.ps1 -GitHubOrg myorg -GitHubRepo digital-twin

.EXAMPLE
    .\scripts\setup-iam.ps1 -GitHubOrg myorg -GitHubRepo digital-twin `
        -RoleName my-deploy-role -PolicyName my-deploy-policy
#>

param(
    [Parameter(Mandatory = $true)]
    [string]$GitHubOrg,

    [Parameter(Mandatory = $true)]
    [string]$GitHubRepo,

    [string]$RoleName    = "github-actions-deploy",
    [string]$PolicyName  = "github-actions-deploy-policy",
    [string]$ProjectName = "twin",
    [string[]]$Environments = @("dev", "test", "prod")
)

$ErrorActionPreference = "Stop"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
function Write-Step  { param([string]$msg) Write-Host "`n$msg" -ForegroundColor Cyan }
function Write-Ok    { param([string]$msg) Write-Host "  ✔  $msg" -ForegroundColor Green }
function Write-Skip  { param([string]$msg) Write-Host "  –  $msg (already exists, skipping)" -ForegroundColor Yellow }
function Write-Info  { param([string]$msg) Write-Host "  ℹ  $msg" -ForegroundColor Gray }

# ---------------------------------------------------------------------------
# Resolve context
# ---------------------------------------------------------------------------
Write-Step "Resolving AWS account identity..."
$AwsAccountId = aws sts get-caller-identity --query Account --output text
Write-Ok "Account ID: $AwsAccountId"

$PolicyArn   = "arn:aws:iam::${AwsAccountId}:policy/${PolicyName}"
$OidcIssuer  = "token.actions.githubusercontent.com"
$OidcArn     = "arn:aws:iam::${AwsAccountId}:oidc-provider/${OidcIssuer}"
# SHA-1 thumbprint of the GitHub Actions OIDC TLS certificate (long-lived root CA)
$Thumbprint  = "6938fd4d98bab03faadb97b34396831e3780aea1"

# Script root resolves correctly whether called from any working directory
$RepoRoot    = Split-Path $PSScriptRoot -Parent
$PolicyFile  = Join-Path $RepoRoot "iam\github-actions-deploy-policy.json"

if (-not (Test-Path $PolicyFile)) {
    Write-Host "  ✖  Policy document not found at: $PolicyFile" -ForegroundColor Red
    exit 1
}

# Read the policy template and substitute the project name into all resource ARN
# patterns (e.g. "twin-*" → "<ProjectName>-*") so the created policy correctly
# scopes to the resources that Terraform will provision under the chosen prefix.
$Utf8NoBomEncoding = New-Object System.Text.UTF8Encoding($false)
$PolicyContent = [System.IO.File]::ReadAllText($PolicyFile)
if ($ProjectName -ne "twin") {
    Write-Info "Substituting project name '$ProjectName' into policy resource patterns..."
    # Replace the 'twin-' prefix that appears in every project-scoped resource ARN.
    # The lookbehind covers the characters that can directly precede 'twin-' in ARNs:
    #   ':' → e.g. "secret:twin-*", "function:twin-*", "s3:::twin-*"
    #   '/' → e.g. "role/twin-*", "table/twin-terraform-locks"
    #   '"' → start of a string value (defensive catch-all)
    $PolicyContent = $PolicyContent -replace '(?<=[":/])twin-', "${ProjectName}-"
}

# ---------------------------------------------------------------------------
# 1. GitHub OIDC identity provider
# ---------------------------------------------------------------------------
Write-Step "Step 1/4 — GitHub OIDC identity provider"

$existingProviders = aws iam list-open-id-connect-providers --query "OpenIDConnectProviderList[].Arn" --output text
if ($existingProviders -like "*${OidcIssuer}*") {
    Write-Skip "OIDC provider $OidcArn"
} else {
    aws iam create-open-id-connect-provider `
        --url "https://${OidcIssuer}" `
        --client-id-list "sts.amazonaws.com" `
        --thumbprint-list $Thumbprint | Out-Null
    Write-Ok "Created OIDC provider: $OidcArn"
}

# ---------------------------------------------------------------------------
# 2. IAM role with trust policy
# ---------------------------------------------------------------------------
Write-Step "Step 2/4 — IAM role: $RoleName"

# Build the list of allowed subjects (one per environment)
$subjects = ($Environments | ForEach-Object {
    "`"repo:${GitHubOrg}/${GitHubRepo}:environment:$_`""
}) -join ",`n            "

$TrustPolicy = @"
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "$OidcArn"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
          "token.actions.githubusercontent.com:sub": [
            $subjects
          ]
        }
      }
    }
  ]
}
"@

$TrustPolicyFile = Join-Path ([System.IO.Path]::GetTempPath()) "trust-policy-$([System.Guid]::NewGuid().ToString('N')).json"
[System.IO.File]::WriteAllText($TrustPolicyFile, $TrustPolicy, $Utf8NoBomEncoding)

try {
    $roleExists = $false
    # Temporarily allow non-zero exit codes so we can distinguish "not found" from a real error
    $ErrorActionPreference = "Continue"
    $existingRoleArn = aws iam get-role --role-name $RoleName --query "Role.Arn" --output text 2>$null
    $ErrorActionPreference = "Stop"
    if ($LASTEXITCODE -eq 0 -and $existingRoleArn) {
        $roleExists = $true
        Write-Skip "IAM role $RoleName ($existingRoleArn)"
    }

    if (-not $roleExists) {
        aws iam create-role `
            --role-name $RoleName `
            --assume-role-policy-document "file://$TrustPolicyFile" `
            --description "GitHub Actions OIDC deploy role for ${GitHubOrg}/${GitHubRepo}" | Out-Null
        Write-Ok "Created IAM role: $RoleName"
    }
} finally {
    $ErrorActionPreference = "Stop"
    Remove-Item $TrustPolicyFile -Force -ErrorAction SilentlyContinue
}

# ---------------------------------------------------------------------------
# 3. Managed IAM policy
# ---------------------------------------------------------------------------
Write-Step "Step 3/4 — Managed IAM policy: $PolicyName"

$existingPolicy = $null
$ErrorActionPreference = "Continue"
$existingPolicyArn = aws iam get-policy --policy-arn $PolicyArn --query "Policy.Arn" --output text 2>$null
$ErrorActionPreference = "Stop"
if ($LASTEXITCODE -eq 0 -and $existingPolicyArn) {
    $existingPolicy = $existingPolicyArn
}

if ($existingPolicy) {
    Write-Skip "Managed policy $PolicyArn"
    if ($ProjectName -ne "twin") {
        Write-Info "Note: the policy was created with '$ProjectName' resource patterns."
        Write-Info "To push an updated version of the policy document, re-run this script"
        Write-Info "and pass -PolicyName with a different name (a new policy will be created),"
        Write-Info "or run the following PowerShell block from the repository root:"
        Write-Info "  `$content = (Get-Content iam\github-actions-deploy-policy.json -Raw) -replace '""twin-', '""${ProjectName}-'"
        Write-Info "  `$tmp = [IO.Path]::GetTempFileName() + '.json'"
        Write-Info "  [IO.File]::WriteAllText(`$tmp, `$content, [Text.UTF8Encoding]::new(`$false))"
        Write-Info "  aws iam create-policy-version --policy-arn `"$PolicyArn`" --set-as-default --policy-document `"file://`$tmp`""
        Write-Info "  Remove-Item `$tmp"
    } else {
        Write-Info "To update the policy document run:"
        Write-Info "  aws iam create-policy-version ``"
        Write-Info "    --policy-arn `"$PolicyArn`" ``"
        Write-Info "    --policy-document file://iam/github-actions-deploy-policy.json ``"
        Write-Info "    --set-as-default"
    }
} else {
    # Write the (possibly substituted) policy content to a temp file so the AWS
    # CLI receives UTF-8 without BOM regardless of the PowerShell version.
    $PolicyTempFile = Join-Path ([System.IO.Path]::GetTempPath()) "deploy-policy-$([System.Guid]::NewGuid().ToString('N')).json"
    try {
        [System.IO.File]::WriteAllText($PolicyTempFile, $PolicyContent, $Utf8NoBomEncoding)
        aws iam create-policy `
            --policy-name $PolicyName `
            --policy-document "file://$PolicyTempFile" `
            --description "Permissions for GitHub Actions to deploy the $ProjectName project" | Out-Null
        Write-Ok "Created managed policy: $PolicyArn"
    } finally {
        Remove-Item $PolicyTempFile -Force -ErrorAction SilentlyContinue
    }
}

# ---------------------------------------------------------------------------
# 4. Attach policy to role
# ---------------------------------------------------------------------------
Write-Step "Step 4/4 — Attaching policy to role"

$attachedPolicies = aws iam list-attached-role-policies `
    --role-name $RoleName `
    --query "AttachedPolicies[].PolicyArn" `
    --output text

if ($attachedPolicies -like "*$PolicyArn*") {
    Write-Skip "Policy already attached to $RoleName"
} else {
    aws iam attach-role-policy `
        --role-name $RoleName `
        --policy-arn $PolicyArn
    Write-Ok "Attached $PolicyName to $RoleName"
}

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
$RoleArn = aws iam get-role --role-name $RoleName --query "Role.Arn" --output text

Write-Host ""
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Green
Write-Host " IAM setup complete!" -ForegroundColor Green
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Green
Write-Host ""
Write-Host " Role ARN  : $RoleArn" -ForegroundColor Cyan
Write-Host " Policy ARN: $PolicyArn" -ForegroundColor Cyan
Write-Host ""
Write-Host " Next steps:" -ForegroundColor Yellow
$envList = $Environments -join "', '"
Write-Host "  1. In GitHub: Settings → Environments → create '$envList'" -ForegroundColor White
Write-Host "  2. Add these secrets to each environment (or at repo level):" -ForegroundColor White
Write-Host "       AWS_ROLE_ARN       = $RoleArn" -ForegroundColor White
Write-Host "       AWS_ACCOUNT_ID     = $AwsAccountId" -ForegroundColor White
Write-Host "       DEFAULT_AWS_REGION = us-east-1  (or your preferred region)" -ForegroundColor White
Write-Host "       OPENAI_API_KEY     = <your OpenAI API key>" -ForegroundColor White
Write-Host ""
Write-Host " The deploy workflow is ready to run!" -ForegroundColor Green
Write-Host ""
