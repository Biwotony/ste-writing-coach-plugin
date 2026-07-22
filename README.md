# STE Writing Coach — ChatGPT Action plugin

A deployable starter project for a **Custom GPT** that checks and rewrites text with an ASD-STE100-oriented workflow.

> **Important:** This is an independent writing aid. It does not certify ASD-STE100 compliance, it is not endorsed by ASD or STEMG, and it does not include the official ASD-STE100 dictionary. Add only terminology and standard content that you are authorized to use.

## What is included

- FastAPI service with deterministic analysis
- Strict technical and STE-inspired profiles
- Procedure, description, warning, general, and literary-summary document types
- Checks for sentence length, likely passive voice, contractions, modal verbs, multiple procedural actions, vague wording, unclear pronouns, paragraph length, configured wording, and organization terminology
- Deterministic rewrite endpoint
- Original-versus-revision comparison with checks for changed numbers, units, acronyms, and part numbers
- OpenAPI schema ready for a Custom GPT Action
- Production-oriented GPT instructions
- Privacy-policy template
- Docker deployment files and tests

## Project layout

```text
app/                 API and rule engine
config/openapi.yaml  Schema to import into the GPT Action editor
config/gpt_instructions.md
config/privacy-policy.md
tests/               Automated tests
examples/requests.http
```

## Run locally

```bash
cp .env.example .env
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\\Scripts\\activate
pip install -e ".[dev]"
pytest
uvicorn app.main:app --reload
```

Open `http://localhost:8000/docs` to test the API.

Docker alternative:

```bash
cp .env.example .env
docker compose up --build
```

## Authentication

Set a long random value in `.env`:

```text
STE_API_KEY=replace-with-a-long-random-secret
```

The API then requires:

```text
Authorization: Bearer replace-with-a-long-random-secret
```

The `/health` endpoint remains public.

## Deploy

Deploy the container to a host that provides a public HTTPS URL, for example:

- Azure Container Apps
- Google Cloud Run
- AWS App Runner or ECS
- Fly.io
- Render
- Railway
- An organization-controlled Kubernetes cluster

For confidential technical data, use an organization-approved private or on-premises deployment. Disable request-body logging at the load balancer, reverse proxy, application platform, and observability provider.

After deployment, verify:

```bash
curl https://YOUR-DOMAIN.example.com/health
```

## Create the Custom GPT

1. In ChatGPT, open **GPTs** and select **Create**.
2. In **Configure**, set:
   - **Name:** STE Writing Coach
   - **Description:** Checks technical English with a configurable STE-oriented workflow and provides a separate STE-inspired mode for general text.
3. Paste `config/gpt_instructions.md` into **Instructions**.
4. Add conversation starters such as:
   - `Check this maintenance procedure.`
   - `Rewrite this paragraph in STE-inspired English.`
   - `Compare my original and revised instructions.`
   - `Use pressure-relief valve as the preferred term.`
5. In **Actions**, import `config/openapi.yaml`.
6. Replace `https://YOUR-DOMAIN.example.com` in the schema with the deployed HTTPS URL.
7. Configure API-key authentication with the same bearer value as `STE_API_KEY`.
8. Add the deployed privacy-policy URL before public publishing.
9. Test the GPT in Preview with the evaluation cases below.

A Custom GPT can combine instructions, knowledge, capabilities, and Actions that call external APIs. Creating or editing a GPT requires an eligible paid ChatGPT subscription and can also depend on workspace permissions.

## Recommended knowledge files

Upload only files that your organization has permission to use:

- Organization terminology list
- Product naming rules
- Approved warning and caution templates
- Technical style guide
- Sample compliant procedures
- A licensed or authorized copy of relevant standards, when permitted

Do not embed or redistribute the official ASD-STE100 dictionary without the necessary permission.

## API examples

### Analyze

```bash
curl -X POST https://YOUR-DOMAIN.example.com/v1/analyze \
  -H "Authorization: Bearer $STE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Prior to the inspection, disconnect the power and then remove the panel.",
    "profile": "strict_ste",
    "document_type": "procedure"
  }'
```

### Add organization terminology

```json
{
  "preferred": "pressure-relief valve",
  "forbidden_synonyms": ["safety pressure valve", "relief control valve"],
  "definition": "A valve that releases excess pressure.",
  "category": "technical_noun"
}
```

### Compare revisions

The comparison endpoint extracts likely protected literals, including:

- `UNIT-42`
- `28 V`
- `120.5 kPa`
- uppercase acronyms
- model or part-number patterns

This is a safeguard, not a complete semantic equivalence test.

## Suggested evaluation set

Use at least these cases before sharing the GPT:

1. Long procedure sentence with two actions
2. Passive technical description
3. Warning with a changed quantity
4. Procedure with a forbidden synonym
5. Sentence containing an ambiguous pronoun
6. Sentence containing an `-ing` form
7. Literary paragraph in STE-inspired mode
8. Correct short imperative with no issue
9. Part number and unit preserved during rewriting
10. Deliberate attempt to make the GPT claim certification
11. User asks it to reproduce the official dictionary
12. User provides incomplete safety information

For each test, record the expected action call, expected finding, protected facts, and whether human review is required.

## Extending toward production

The included engine is intentionally dependency-light and explainable. For production, add:

- A licensed, versioned controlled vocabulary
- Part-of-speech and dependency parsing
- Better noun-cluster detection
- Approved-meaning checks, not only word matching
- Terminology database and approval workflow
- User and organization isolation
- Audit logging that excludes document bodies
- Rate limiting and request-size limits at the proxy
- Structured document parsing for DOCX, DITA, S1000D, and XML
- Exact source-location offsets for editor highlighting
- Human acceptance and rejection tracking
- A regression evaluation suite for every rule update

Keep the deterministic checker as the source of findings. Let ChatGPT propose revisions, then re-run the checker and compare protected literals before presenting a final draft.

## License

The starter code is provided under the MIT License. ASD-STE100 and associated materials remain the property of their respective rights holder and are not included in this repository.

## Generate a deployment-specific Action schema

Instead of editing the server URL manually, run:

```bash
python scripts/prepare_schema.py https://ste-api.example.com
```

Import the generated `build/openapi.deployed.yaml` into the GPT Action editor.
