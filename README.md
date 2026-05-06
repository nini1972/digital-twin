# AI Digital Twin

A serverless AI chatbot that lives on your professional website and represents *you*. Visitors can have a real conversation with your digital twin — powered by **AWS Bedrock** — as if they were speaking directly with you.

```
Visitor's browser
  │                 │
  │ serves frontend │ calls chat API
  ▼                 ▼
CloudFront CDN   API Gateway (HTTP)
  │                 │
  ▼                 ▼
S3 (Next.js      AWS Lambda (Python / FastAPI)
static site)        │                     │
                    ▼                     ▼
               AWS Bedrock         S3 (per-session conversation memory)
               (Nova LLM)
```

---

## Features

- **Conversational AI** — multi-turn chat with full session memory stored in S3
- **Your persona** — the AI is briefed with your LinkedIn profile, a bio summary, your communication style, and key facts
- **Jailbreak-resistant** — the system prompt instructs the model to refuse prompt-injection attempts
- **Fully serverless** — Lambda + API Gateway, scales to zero when idle
- **One-command deploy** — a single script builds the Lambda package, runs Terraform, and syncs the frontend to S3
- **Optional custom domain** — supports Route 53 + ACM certificate setup for a custom domain
- **Agentic EV Micro-Twin** — a live multi-agent city simulation (resident EVs + charging hubs) runs in the background; the Oracle AI can observe and manipulate it in real time via tool calling

---

## Prerequisites

| Tool | Purpose |
|---|---|
| [AWS CLI](https://aws.amazon.com/cli/) ≥ v2 | AWS authentication and S3 sync |
| [Terraform](https://www.terraform.io/) ≥ 1.5 | Infrastructure provisioning |
| [Docker](https://www.docker.com/) | Building the Lambda deployment package |
| [uv](https://docs.astral.sh/uv/) | Python package manager for the backend |
| [Node.js](https://nodejs.org/) ≥ 20 | Next.js frontend |

Your AWS credentials must have permissions for: Lambda, API Gateway, S3, CloudFront, IAM, Bedrock, DynamoDB, Secrets Manager, and (optionally) Route 53 and ACM.

You must also **enable the Bedrock model** you plan to use in the [AWS Bedrock console](https://console.aws.amazon.com/bedrock/home#/modelaccess) before deploying.

---

## Project Structure

```
digital-twin/
├── backend/
│   ├── data/                   # Your personal data (see "Personalising Your Twin")
│   │   ├── facts.json          # Key facts (name, role, location, …)
│   │   ├── summary.txt         # Free-form professional bio
│   │   ├── style.txt           # Communication style notes
│   │   └── linkedin.pdf        # LinkedIn profile export
│   ├── server.py               # FastAPI application
│   ├── lambda_handler.py       # Mangum adapter for AWS Lambda
│   ├── context.py              # Builds the AI system prompt from your data
│   ├── resources.py            # Loads the data files at startup
│   ├── simulation.py           # Multi-agent EV city simulation (agents + engine)
│   ├── database.py             # SQLite helpers (conversations, telemetry, market events)
│   ├── deploy.py               # Packages the Lambda deployment zip
│   ├── pyproject.toml          # Python dependencies (managed by uv)
│   └── requirements.txt        # Pinned requirements for Lambda packaging
├── frontend/
│   ├── app/
│   │   ├── twin/               # /twin route — cinematic landing / welcome page
│   │   ├── chat/               # /chat route — the main chat interface
│   │   ├── simulation/         # /simulation route — live EV city simulation dashboard
│   │   └── page.tsx            # Root redirect → /twin
│   ├── components/
│   │   └── twin.tsx            # Chat UI component (mounted at /chat)
│   └── public/
│       ├── digital-twin-hero.mp4   # Hero video played on the /twin landing page
│       ├── digital-twin-sound.mp3  # Ambient audio synced to the hero video
│       ├── avatar.png              # Your photo — avatar shown in the chat interface
│       ├── avatar-blink.mp4        # Short blink animation shown before the avatar appears
│       └── favicon-180v2.png       # Brand icon displayed in the chat header
├── terraform/
│   ├── main.tf                 # All AWS resources
│   ├── variables.tf            # Variable definitions
│   ├── outputs.tf              # Deployment outputs (URLs, bucket names)
│   ├── backend.tf              # S3 remote state configuration
│   ├── terraform.tfvars        # Default variable values (dev)
│   └── prod.tfvars             # Production overrides
├── scripts/
│   ├── deploy.sh               # Full deploy (Linux / macOS)
│   ├── deploy.ps1              # Full deploy (Windows)
│   ├── destroy.sh              # Tear down all AWS resources (Linux / macOS)
│   └── destroy.ps1             # Tear down all AWS resources (Windows)
├── .github/
│   └── workflows/
│       ├── deploy.yml          # CI/CD — deploy on push to main or manual dispatch
│       └── destroy.yml         # Manual workflow to tear down an environment
└── .env.example                # Environment variable template
```

---

## Personalising Your Twin

Before you can run or deploy the project you need to populate your personal data files in `backend/data/`.

### `facts.json`

Key facts the AI always has in context:

```json
{
  "full_name": "Jane Smith",
  "name": "Jane",
  "role": "Senior Software Engineer",
  "location": "London, UK",
  "email": "jane@example.com"
}
```

### `summary.txt`

A free-form professional bio — career highlights, current focus areas, notable projects. A few paragraphs is enough.

### `style.txt`

Notes about how you communicate — tone, things you care about, phrases you like or dislike. The AI uses these to match your voice.

### `linkedin.pdf`

Export your LinkedIn profile as a PDF (**Me → Resources → Save to PDF**) and place it here. The AI reads your full work history and skills from this file.

### Frontend media assets

Place these files in `frontend/public/`. They are required by the default frontend and are split across the two routes:

**Landing page (`/twin`)**

| File | Description |
|---|---|
| `digital-twin-hero.mp4` | Full-screen hero video that plays when visitors first arrive. The "Enter the Room" button appears once this video ends. |
| `digital-twin-sound.mp3` | Ambient audio that plays in sync with the hero video (auto-unlocked on the first user interaction). |

**Chat interface (`/chat`)**

| File | Description |
|---|---|
| `avatar.png` | Your photo, shown as the AI's avatar throughout the chat view and during the welcome sequence. |
| `avatar-blink.mp4` | Short blink animation played just before the static avatar fades in. The chat welcome sequence advances when this video ends. |
| `favicon-180v2.png` | Brand icon displayed in the chat header. |

> Note: None of these assets are optional in the default frontend implementation — omitting any of them will break the corresponding part of the UI unless you update the frontend accordingly.

---

## Local Development

### 1. Configure environment variables

```bash
cp .env.example .env
# Edit .env and fill in your AWS account ID and region
```

### 2. Start the backend

```bash
cd backend
uv sync                         # Install dependencies
uv run uvicorn server:app --reload
```

The API is now available at `http://localhost:8000`.

By default, conversation history is stored in the `memory/` directory (relative to the project root). Set `USE_S3=true` and `S3_BUCKET=<bucket>` in `.env` to use S3 instead.

### 3. Start the frontend

```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:3000/twin](http://localhost:3000/twin) for the landing page experience, [http://localhost:3000/chat](http://localhost:3000/chat) for the chat interface, or [http://localhost:3000/simulation](http://localhost:3000/simulation) for the live simulation dashboard. The chat calls `http://127.0.0.1:8000` by default — override with `NEXT_PUBLIC_API_URL` in `frontend/.env.local`.

### Backend API endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/` | Service info |
| `GET` | `/health` | Health check |
| `POST` | `/chat` | Send a message, receive a reply |
| `GET` | `/conversation/{session_id}` | Retrieve conversation history |
| `GET` | `/api/telemetry` | Historical simulation telemetry and market events |
| `WebSocket` | `/ws/simulation` | Real-time simulation state stream |

---

## GitHub Actions CI/CD

The repository ships with two GitHub Actions workflows that automate deployment and teardown — no need to run scripts locally once the pipeline is set up.

### Workflows

| Workflow | File | Trigger |
|---|---|---|
| **Deploy Digital Twin** | `.github/workflows/deploy.yml` | Push to `main` (→ `dev`) or manual dispatch with environment choice |
| **Destroy Environment** | `.github/workflows/destroy.yml` | Manual dispatch only — requires typing the environment name to confirm |

#### Deploy workflow
- Triggered automatically on every push to `main` (deploys to `dev`).
- Can also be triggered manually from the **Actions** tab to deploy to `dev`, `test`, or `prod`.
- Uses OIDC to assume an IAM role — no long-lived AWS credentials are stored in GitHub.
- After Terraform applies, CloudFront is automatically invalidated to serve the latest frontend.

#### Destroy workflow
- Manual only. You must select an environment **and** type its name again to confirm — a deliberate safety gate.

### One-time GitHub setup

#### 1. Create GitHub Environments

In your repository go to **Settings → Environments** and create three environments: `dev`, `test`, and `prod`. Add the secrets below to each environment (or at the repository level if they are shared across all environments):

| Secret | Description |
|---|---|
| `AWS_ROLE_ARN` | ARN of the IAM role the workflow will assume (e.g. `arn:aws:iam::123456789012:role/github-actions-deploy`) |
| `AWS_ACCOUNT_ID` | Your 12-digit AWS account ID |
| `DEFAULT_AWS_REGION` | AWS region, e.g. `us-east-1` |
| `OPENAI_API_KEY` | OpenAI API key used by the Lambda chat endpoint |

#### 2. Create an IAM role for OIDC

The workflow uses `aws-actions/configure-aws-credentials` with `role-to-assume`. You need an IAM role that trusts the GitHub Actions OIDC provider.

**Recommended — automated setup (Windows / PowerShell):**

```powershell
.\scripts\setup-iam.ps1 -GitHubOrg YOUR_GITHUB_ORG -GitHubRepo YOUR_REPO_NAME
```

This script is idempotent: it skips any resources that already exist and prints the role ARN and next steps when it finishes.

**Manual setup (bash):**

```bash
# 1. Add the GitHub OIDC provider to your account (once per account)
aws iam create-open-id-connect-provider \
  --url https://token.actions.githubusercontent.com \
  --client-id-list sts.amazonaws.com \
  --thumbprint-list 6938fd4d98bab03faadb97b34396831e3780aea1

# 2. Create the IAM role with a trust policy that allows your repo to assume it
# Replace YOUR_ACCOUNT_ID, YOUR_GITHUB_ORG, and YOUR_REPO_NAME in all three places below
cat > trust-policy.json <<'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::YOUR_ACCOUNT_ID:oidc-provider/token.actions.githubusercontent.com"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
          "token.actions.githubusercontent.com:sub": [
            "repo:YOUR_GITHUB_ORG/YOUR_REPO_NAME:environment:dev",
            "repo:YOUR_GITHUB_ORG/YOUR_REPO_NAME:environment:test",
            "repo:YOUR_GITHUB_ORG/YOUR_REPO_NAME:environment:prod"
          ]
        }
      }
    }
  ]
}
EOF

aws iam create-role \
  --role-name github-actions-deploy \
  --assume-role-policy-document file://trust-policy.json
```

Attach a scoped custom policy that covers all services used during deployment (Lambda, API Gateway, S3, CloudFront, IAM, Bedrock, DynamoDB, and Secrets Manager). A ready-to-use policy document is provided at `iam/github-actions-deploy-policy.json`:

```bash
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

# Create the managed policy from the provided document (first time only)
aws iam create-policy \
  --policy-name github-actions-deploy-policy \
  --policy-document file://iam/github-actions-deploy-policy.json

# Attach it to the role
aws iam attach-role-policy \
  --role-name github-actions-deploy \
  --policy-arn "arn:aws:iam::${AWS_ACCOUNT_ID}:policy/github-actions-deploy-policy"
```

> **Note:** `aws iam create-policy` is a one-time operation per AWS account. If the policy already exists you will get `EntityAlreadyExists` — that is expected and safe to ignore. To update the policy document later use `aws iam create-policy-version` instead (see [Troubleshooting](#troubleshooting)).

> **Important:** Before Terraform runs, the deploy script writes the OpenAI API key to AWS Secrets Manager. By default, with `project_name = "twin"`, the secret name pattern is `twin-<env>-openai-api-key`, so the role **must** have `secretsmanager:DescribeSecret`, `secretsmanager:CreateSecret`, and `secretsmanager:PutSecretValue` on secrets matching `twin-*` — without these the deployment will fail with an `AccessDeniedException`. If you override `project_name`, the secret name changes accordingly, so you must also update the Secrets Manager resource pattern in `iam/github-actions-deploy-policy.json` (and any equivalent custom policy) to match your chosen prefix instead of `twin-*`.

> **Optional Route 53 / ACM:** If you enable `use_custom_domain = true`, also attach `arn:aws:iam::aws:policy/AmazonRoute53FullAccess` and `arn:aws:iam::aws:policy/AWSCertificateManagerFullAccess` to the role.

---

## AWS Deployment

### One-time bootstrap: Terraform remote state

The deploy script uses an S3 bucket and a DynamoDB table for Terraform state. Create them once before your first deploy:

```bash
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
AWS_REGION=us-east-1   # change if needed

# S3 bucket for state
aws s3 mb "s3://twin-terraform-state-${AWS_ACCOUNT_ID}" --region $AWS_REGION
aws s3api put-bucket-versioning \
  --bucket "twin-terraform-state-${AWS_ACCOUNT_ID}" \
  --versioning-configuration Status=Enabled

# DynamoDB table for state locking
aws dynamodb create-table \
  --table-name twin-terraform-locks \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region $AWS_REGION
```

### Deploy to dev

```bash
bash scripts/deploy.sh dev twin
```

After a successful deploy, the script prints:

```
✅ Deployment complete!
🌐 CloudFront URL : https://xxxxxxxxxxxx.cloudfront.net
📡 API Gateway    : https://xxxxxxxxxx.execute-api.us-east-1.amazonaws.com
```

### Deploy to production (with a custom domain)

1. Make sure your domain is hosted in **Route 53**.
2. Edit `terraform/prod.tfvars`:

```hcl
use_custom_domain = true
root_domain       = "yourdomain.com"
bedrock_model_id  = "amazon.nova-pro-v1:0"
```

3. Deploy:

```bash
bash scripts/deploy.sh prod twin
```

Terraform will request an ACM certificate, create the DNS validation records, and wire up Route 53 alias records for CloudFront. The certificate still must be issued in **us-east-1**. On a fresh production deploy, ACM issuance can take time, so the first apply/deploy may need to be rerun after DNS validation completes and the certificate is issued.

### Tear down

```bash
bash scripts/destroy.sh dev twin
# or
bash scripts/destroy.sh prod twin
```

> **Note:** The provided destroy scripts automatically empty the frontend and memory S3 buckets before running `terraform destroy`.

---

## Configuration Reference

### Terraform variables (`terraform/terraform.tfvars`)

| Variable | Default | Description |
|---|---|---|
| `project_name` | `twin` | Prefix for all AWS resource names |
| `environment` | `dev` | Deployment environment (`dev`, `test`, `prod`) |
| `bedrock_model_id` | `amazon.nova-pro-v1:0` | Bedrock model to use |
| `lambda_timeout` | `60` | Lambda timeout in seconds |
| `api_throttle_burst_limit` | `10` | API Gateway burst throttle limit |
| `api_throttle_rate_limit` | `5` | API Gateway steady-state throttle (req/s) |
| `use_custom_domain` | `false` | Attach a custom domain to CloudFront |
| `root_domain` | `""` | Apex domain (e.g. `mydomain.com`) |

### Available Bedrock models

| Model ID | Speed | Cost | Best for |
|---|---|---|---|
| `amazon.nova-micro-v1:0` | Fastest | Lowest | Development / testing |
| `amazon.nova-lite-v1:0` | Fast | Low | General use |
| `amazon.nova-pro-v1:0` | Moderate | Higher | Production |

> Some regions require a `us.` or `eu.` prefix, e.g. `us.amazon.nova-pro-v1:0`. Check the [Bedrock documentation](https://docs.aws.amazon.com/bedrock/latest/userguide/models-regions.html) for your region.

### Backend environment variables (`.env`)

> **Note:** The current backend uses **OpenAI** for chat and tool calling (not AWS Bedrock). Bedrock model variables in `terraform/terraform.tfvars` are retained for infrastructure compatibility, while the FastAPI application uses AWS configuration for other AWS clients such as S3 via `boto3`.

| Variable | Default | Description |
|---|---|---|
| `AWS_ACCOUNT_ID` | — | Your 12-digit AWS account ID |
| `DEFAULT_AWS_REGION` | `us-east-1` | AWS region for backend AWS clients such as S3 (via `boto3`) |
| `OPENAI_API_KEY` | — | OpenAI API key used by the Oracle AI |
| `LLM_MODEL_ID` | `gpt-4o-mini` | OpenAI model ID for chat and tool calling |
| `ALLOW_CODE_EXECUTION` | `false` | Enable the Oracle's `execute_python` tool. **Only set to `true` in trusted, local environments** — arbitrary Python code runs with server-level access. Never enable in production. |
| `USE_S3` | `false` | Use S3 for conversation storage instead of local files |
| `S3_BUCKET` | — | S3 bucket name (required when `USE_S3=true`) |
| `MEMORY_DIR` | `../memory` | Local directory for conversation files (when `USE_S3=false`) |
| `CORS_ORIGINS` | `http://localhost:3000` | Comma-separated list of allowed origins |

### Frontend environment variables

| Variable | Default | Description |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | Backend API base URL |

Set this in `frontend/.env.local` for local development. The deploy script creates `frontend/.env.production` automatically during deployment.

---

## Simulation — Agentic EV Micro-Twin

A live, multi-agent city simulation runs in the background whenever the backend is running. Resident electric vehicles (EVs) navigate a 100 × 100 virtual city grid, autonomously seeking and queuing at charging hubs. The Oracle AI (your digital twin's alter ego) can observe the simulation in real time and manipulate it through tool calling.

### How it works

The simulation runs as a background `asyncio` task started by the FastAPI lifespan. Every **0.5 seconds** (one tick) the engine:

1. Frees completed charging slots and promotes waiting residents into free slots.
2. Steps every resident agent (move, drain battery, seek hubs).
3. Updates hub pricing based on demand.
4. Logs telemetry to SQLite every 10 ticks and fires automated market events every 20 ticks.
5. Broadcasts the full city state to all connected WebSocket clients.

### Agent types

#### `ResidentAgent` — autonomous EV car

Each resident has a position, battery level, speed, and a `ResidentState`:

| State | Description |
|---|---|
| `DRIVING` | Moving toward a random destination; battery draining each tick |
| `SEEKING` | Battery below threshold — heading for the best-scored hub |
| `WAITING` | Arrived at hub, queued for a free charging slot |
| `CHARGING` | In a slot; battery refilling each tick until full (→ back to DRIVING) |

When the battery drops below **30 %** (or **40 %** during a storm/extreme heat), the resident scores all active hubs by `distance² × distance_weight + price × price_weight` and steers toward the best option.

#### `ChargingHubAgent` — EV charging station

Each hub has a fixed capacity of **4 simultaneous charging slots** and a dynamic electricity price (default **$0.20 / kWh**):

- If total demand (charging + waiting) exceeds 2, the price ticks **+$0.01** per tick.
- If demand reaches 0 and price is above $0.15, the price ticks **−$0.01** per tick.
- Automated market events can trigger larger price surges or drops every 20 ticks.

### Oracle AI tools

The Oracle (your digital twin) has god-like powers over the simulation, exposed as OpenAI tool-call functions:

| Tool | What it does |
|---|---|
| `add_resident_agents` | Spawn N new EV agents in random positions |
| `add_charging_hubs` | Add N new charging hubs at random positions |
| `trigger_surge_event` | Drain the battery of a random % of residents to a critical level (≤20 %) |
| `set_global_parameters` | Tune `charging_speed`, `battery_drain`, `distance_weight`, and `price_weight` |
| `set_weather` | Switch weather (`sunny` / `storm` / `extreme_heat`) — affects drain rate and charging speed |
| `trigger_maintenance` | Randomly disable one active hub to simulate hardware failure |
| `set_hub_price` | Manually override the electricity price of a specific hub |
| `execute_python` | Run an arbitrary Python snippet with `engine` in scope (requires `ALLOW_CODE_EXECUTION=true`) ⚠️ **Never enable in production** |

**Weather effects**

| Condition | Battery drain / tick | Charging speed / tick | Seek threshold |
|---|---|---|---|
| `sunny` (default) | 0.2 % | 5.0 % | 30 % |
| `storm` | 0.5 % | 2.0 % | 40 % |
| `extreme_heat` | 0.8 % | 4.0 % | 40 % |

### Simulation API endpoints

| Method | Path | Description |
|---|---|---|
| `WebSocket` | `/ws/simulation` | Real-time state stream; also accepts `add_hub` / `add_resident` text commands |
| `GET` | `/api/telemetry?limit=50` | Historical telemetry rows and recent market events (SQLite) |

### Data persistence

Simulation telemetry/event data is stored in a local SQLite database at `backend/data/simulation.db`. Conversation history is environment-dependent: when `USE_S3=true`, it is stored in S3 as per-session JSON; otherwise it is stored locally in the development conversation-memory directory.

| Store / Table | Columns | Populated by |
|---|---|---|
| `conversations` (S3 or local JSON; if SQLite-backed, includes internal PK `id`) | `id` (internal PK), `session_id`, `role`, `content`, `timestamp` | `/chat` endpoint |
| `telemetry` (SQLite) | `id` (internal PK), `timestamp`, `weather`, `active_hubs`, `avg_price`, `total_queue` | Every 10 ticks |
| `market_events` (SQLite) | `id` (internal PK), `timestamp`, `event_type`, `description` | Every 20 ticks (`high_demand_surge` / `low_demand_drop`) |

### Simulation dashboard

Navigate to [http://localhost:3000/simulation](http://localhost:3000/simulation) while the backend is running to see:

- **Live city canvas** — animated dots for EVs (color-coded by state) and hub icons with real-time queue and slot occupancy.
- **Movement trails** — toggleable path history showing where each agent has been.
- **Oracle chat panel** — talk to the AI; it reads live telemetry and can fire any of the tools above in response to natural-language commands (e.g. *"trigger a storm"*, *"add 5 more residents"*).
- **Sparkline charts** — rolling history of average hub price and total queue depth fetched from `/api/telemetry`.

---

## Troubleshooting

### GitHub Actions / IAM setup

#### `NoSuchEntity` when updating the policy

Running `aws iam create-policy-version` fails with `NoSuchEntity` if the managed policy has never been created in your account. `create-policy-version` only works against an **existing** policy; `create-policy` must be run first.

Use the provided setup script to do everything in one step:

```powershell
.\scripts\setup-iam.ps1 -GitHubOrg YOUR_ORG -GitHubRepo YOUR_REPO
```

Or run the bootstrap manually:

**Bash:**

```bash
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

# First-time only: create the policy
aws iam create-policy \
  --policy-name github-actions-deploy-policy \
  --policy-document file://iam/github-actions-deploy-policy.json

# Subsequent updates: create a new version and set it as default
aws iam create-policy-version \
  --policy-arn "arn:aws:iam::${AWS_ACCOUNT_ID}:policy/github-actions-deploy-policy" \
  --policy-document file://iam/github-actions-deploy-policy.json \
  --set-as-default
```

**PowerShell:**

```powershell
$AccountId = aws sts get-caller-identity --query Account --output text

# First-time only: create the policy
aws iam create-policy `
  --policy-name github-actions-deploy-policy `
  --policy-document file://iam/github-actions-deploy-policy.json

# Subsequent updates: create a new version and set it as default
aws iam create-policy-version `
  --policy-arn "arn:aws:iam::${AccountId}:policy/github-actions-deploy-policy" `
  --policy-document file://iam/github-actions-deploy-policy.json `
  --set-as-default
```

#### `EntityAlreadyExists` errors

Re-running the setup commands after they have already succeeded will produce `EntityAlreadyExists` for the OIDC provider, role, or policy. These are safe to ignore — the resources are already in place. The `scripts/setup-iam.ps1` script handles this automatically by skipping resources that already exist.

#### `AccessDeniedException` for Secrets Manager during deploy

The deploy script writes the OpenAI API key to Secrets Manager before Terraform runs. If the deploy role is missing Secrets Manager permissions you will see:

```
❌ Error accessing Secrets Manager for 'twin-dev-openai-api-key':
   AccessDeniedException: ...
```

Ensure the role has `secretsmanager:DescribeSecret`, `secretsmanager:CreateSecret`, and `secretsmanager:PutSecretValue` on `arn:aws:secretsmanager:*:*:secret:twin-*`. These permissions are included in `iam/github-actions-deploy-policy.json`. If you customised `project_name` in `terraform.tfvars` (e.g. `myapp`), update the resource pattern in the policy to `arn:aws:secretsmanager:*:*:secret:myapp-*` and then issue a new policy version (see above).

#### Workflow fails with `credentialsClient - assuming role failed`

Ensure the `token.actions.githubusercontent.com` OIDC provider exists in your AWS account **and** that the trust policy on the role lists the correct GitHub org, repo, and environment names. Re-run `scripts/setup-iam.ps1` with the correct `-GitHubOrg` and `-GitHubRepo` values if in doubt.

#### `AWS_ROLE_ARN` secret not set

The deploy workflow reads `AWS_ROLE_ARN` from a GitHub environment secret. If it is missing the `configure-aws-credentials` step will fail immediately. Add the secret under **Settings → Environments → \<env\> → Secrets** (or at repository level). The role ARN is printed at the end of `scripts/setup-iam.ps1` and follows the pattern `arn:aws:iam::<ACCOUNT_ID>:role/github-actions-deploy`.

---

## Architecture Notes

- **Conversation memory** — each browser session gets a UUID; messages are stored as JSON (`<session_id>.json`) in S3 (production) or a local directory (development). The last 20 messages (10 exchanges) are sent to Bedrock to keep costs predictable.
- **Lambda packaging** — `backend/deploy.py` runs dependencies through the official AWS Lambda Python 3.12 Docker image to ensure binary compatibility, then zips everything into `lambda-deployment.zip`.
- **Mangum adapter** — `lambda_handler.py` wraps the FastAPI app with [Mangum](https://mangum.fastapiexpert.com/), which translates API Gateway HTTP events into ASGI calls.
- **CloudFront SPA routing** — a custom error response maps all 404s back to `index.html` so Next.js client-side routing works correctly.
