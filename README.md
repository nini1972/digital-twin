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

---

## Prerequisites

| Tool | Purpose |
|---|---|
| [AWS CLI](https://aws.amazon.com/cli/) ≥ v2 | AWS authentication and S3 sync |
| [Terraform](https://www.terraform.io/) ≥ 1.5 | Infrastructure provisioning |
| [Docker](https://www.docker.com/) | Building the Lambda deployment package |
| [uv](https://docs.astral.sh/uv/) | Python package manager for the backend |
| [Node.js](https://nodejs.org/) ≥ 20 | Next.js frontend |

Your AWS credentials must have permissions for: Lambda, API Gateway, S3, CloudFront, IAM, Bedrock, DynamoDB, and (optionally) Route 53 and ACM.

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
│   ├── deploy.py               # Packages the Lambda deployment zip
│   ├── pyproject.toml          # Python dependencies (managed by uv)
│   └── requirements.txt        # Pinned requirements for Lambda packaging
├── frontend/
│   ├── app/
│   │   ├── twin/               # Current /twin route implementation (landing page)
│   │   └── page.tsx            # Root redirect → /twin
│   ├── components/
│   │   └── twin.tsx            # Reusable chat UI component source (not currently mounted)
│   └── public/
│       ├── avatar.png          # Your photo (required by the current chat UI)
│       └── avatar-blink.mp4    # Short animated avatar video (required by the current welcome/chat UI)
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

Place these files in `frontend/public/`. In the current frontend, these assets are required for the default welcome and chat experience:

| File | Description |
|---|---|
| `avatar.png` | Your photo, rendered as the AI's avatar in the welcome and chat views. |
| `avatar-blink.mp4` | A short video used during the welcome animation (for example, a blinking avatar). The current welcome flow advances when this video finishes, so provide this file unless you also update the frontend to add a real fallback path. |

> Note: These assets are not currently optional in the default frontend implementation.

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

Open [http://localhost:3000/chat](http://localhost:3000/chat) to access the working chat UI. The chat calls `http://localhost:8000` by default — override with `NEXT_PUBLIC_API_URL` in `frontend/.env.local`.

### Backend API endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/` | Service info |
| `GET` | `/health` | Health check |
| `POST` | `/chat` | Send a message, receive a reply |
| `GET` | `/conversation/{session_id}` | Retrieve conversation history |

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

| Variable | Default | Description |
|---|---|---|
| `AWS_ACCOUNT_ID` | — | Your 12-digit AWS account ID |
| `DEFAULT_AWS_REGION` | `us-east-1` | AWS region for Bedrock and other clients |
| `BEDROCK_MODEL_ID` | `amazon.nova-lite-v1:0` | Bedrock model ID |
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

## Architecture Notes

- **Conversation memory** — each browser session gets a UUID; messages are stored as JSON (`<session_id>.json`) in S3 (production) or a local directory (development). The last 20 messages (10 exchanges) are sent to Bedrock to keep costs predictable.
- **Lambda packaging** — `backend/deploy.py` runs dependencies through the official AWS Lambda Python 3.12 Docker image to ensure binary compatibility, then zips everything into `lambda-deployment.zip`.
- **Mangum adapter** — `lambda_handler.py` wraps the FastAPI app with [Mangum](https://mangum.fastapiexpert.com/), which translates API Gateway HTTP events into ASGI calls.
- **CloudFront SPA routing** — a custom error response maps all 404s back to `index.html` so Next.js client-side routing works correctly.
