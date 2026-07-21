# GridMind AI — Cloud Deployment Guide (Railway)

This document provides step-by-step instructions to deploy the GridMind AI system on **Railway**. The application consists of two containerized services:
1. **Node.js Gateway Service** (servers static frontend files and routes client requests).
2. **FastAPI Python RAG Service** (runs the retrieval and generation pipeline).

---

## 📋 Prerequisites

Before starting, ensure you have:
1. A **Railway Account** (sign up at [railway.app](https://railway.app)).
2. A **GitHub Repository** containing this codebase.
3. Your external service keys ready:
   - **Groq API Key** (Llama-3.3 LLM generation)
   - **Voyage AI API Key** (voyage-3.5 embedding generation)
   - **ChromaDB Cloud** Tenant, Database, and API key credentials

---

## 🐳 Local Container Verification (Optional)

To verify the Docker environment works locally before pushing, you can spin up the services using `docker compose`:

1. Copy `.env.example` to `.env` in the project root:
   ```bash
   cp .env.example .env
   ```
2. Populate the `.env` file with your real API keys.
3. Build and run the containers:
   ```bash
   docker compose up --build
   ```
4. Test the gateway at `http://localhost:5000` and Python service health at `http://localhost:8000/health`.

---

## 🚀 Step-by-Step Railway Deployment

Follow these steps to deploy both services from your GitHub repository onto a single Railway project.

### 1. Create a New Railway Project
1. Log in to [Railway](https://railway.app).
2. Click **New Project** in the upper-right corner.
3. Choose **Deploy from GitHub repo**.
4. Select your `gridmind-ai` repository.

### 2. Configure the Python RAG Service
Once you connect the repository, Railway will initialize a default service. We will set this service to build and run the Python backend first:

1. Click on the newly created service card in the canvas.
2. Go to **Settings** → **General**:
   - Rename the service to `rag-service`.
3. Go to **Settings** → **Build**:
   - **Root Directory**: Set to `/` (repository root).
   - **Dockerfile Path**: Set to `backend-python/Dockerfile`.
4. Go to **Variables** and add the following environment variables:

| Variable Name | Value / Description |
|---|---|
| `GROQ_API_KEY` | *Your Groq API Key* |
| `VOYAGE_API_KEY` | *Your Voyage AI API Key* |
| `CHROMA_API_KEY` | *Your ChromaDB Cloud API Key* |
| `CHROMA_TENANT` | *Your ChromaDB Cloud Tenant ID* |
| `CHROMA_DATABASE` | `chroma-rag` |
| `ANONYMOUS_TELEMETRY` | `False` |

Railway automatically injects a dynamic port under the `PORT` variable. The container's start script binds to this port automatically using `uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}`.

### 3. Configure the Node.js Gateway Service
Now, add the Node gateway to the same project:

1. In the Railway canvas, click **+ New** (or right-click the canvas) and select **GitHub Repo**.
2. Select your `gridmind-ai` repository again.
3. Click on this second service card and go to **Settings** → **General**:
   - Rename the service to `gateway-service`.
4. Go to **Settings** → **Build**:
   - **Root Directory**: Set to `/` (repository root).
   - **Dockerfile Path**: Set to `backend-node/Dockerfile`.
5. Go to **Variables** and add the following environment variables:

| Variable Name | Value / Description |
|---|---|
| `RAG_SERVICE_URL` | `http://rag-service.railway.internal:8000` |

> [!IMPORTANT]
> **Railway Private Networking**: Railway exposes services internally to other services in the same project using the pattern `http://<service-name>.railway.internal:<port>`. Because our `rag-service` exposes port `8000`, the URL is `http://rag-service.railway.internal:8000`.

### 4. Expose the Gateway Service to the Internet
The frontend is served by the Node.js gateway, so we need a public URL for it:

1. Select the `gateway-service` card.
2. Go to **Settings** → **Networking**.
3. Under **Public Networking**, click **Generate Domain** (or set a custom domain).
4. Railway will provide a public URL (e.g., `https://gateway-service-production.up.railway.app`).

---

## 🔍 Verification & Testing

Once both services finish deploying, verify that they are running and connected properly:

### 1. Test Gateway Health Endpoint
In your browser, visit the `/health` endpoint of your public URL:
`https://<your-gateway-domain>.up.railway.app/health`

It should make a request to the Python backend internally and return:
```json
{
  "status": "ok",
  "rag": true,
  "llm": true
}
```
If you see `"status": "degraded"`, it means the gateway cannot reach the python service. Check the `RAG_SERVICE_URL` environment variable value and your `rag-service` name on Railway.

### 2. Verify Client-Side RAG Indicator
1. Open the public URL: `https://<your-gateway-domain>.up.railway.app/`
2. Look at the status badge at the top of the chat interface:
   - It should show a green **RAG Active** indicator.
3. Test a quick Kenyan energy policy question (e.g., *"What is the main objective of the Energy Act 2019?"*). Confirm that the answer contains citations citing files from the document library.
