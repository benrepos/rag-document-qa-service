         # RAG Document Chatbot

A production-ready RAG (Retrieval-Augmented Generation) chatbot API built with FastAPI, LangChain, and OpenAI.

## Features

- 📄 Upload PDF/TXT documents and chat with them
- 🔍 Semantic search using FAISS vector store
- 💬 Conversational memory for follow-up questions
- 🚀 Production-ready with Docker support
- 🔒 CORS, file size validation, and health checks

## Quick Start

### Local Development

1. **Install dependencies:**
```bash
pip install -r requirements.txt
```

2. **Set environment variables:**
```bash
export OPENAI_API_KEY=sk-your-key-here
```

3. **Run the server:**
```bash
uvicorn api:app --reload
```

Visit `http://localhost:8000/docs` for interactive API documentation.

### Docker

1. **Build the image:**
```bash
docker build -t rag-chatbot .
```

2. **Run the container:**
```bash
docker run -p 8000:8000 \
  -e OPENAI_API_KEY=sk-your-key-here \
  rag-chatbot
```

## API Endpoints

### `POST /upload`
Upload a document for a user.

**Form data:**
- `user_id`: string
- `file`: PDF or TXT file (max 10MB)

**Response:**
```json
{
  "status": "ok",
  "chunks": 42,
  "filename": "document.pdf"
}
```

### `POST /ask`
Single-turn Q&A (no conversation history).

**Body:**
```json
{
  "user_id": "user123",
  "question": "What is this document about?"
}
```

**Response:**
```json
{
  "answer": "This document is about..."
}
```

### `POST /chat`
Conversational Q&A with memory.

**Body:**
```json
{
  "user_id": "user123",
  "message": "Tell me more about that"
}
```

**Response:**
```json
{
  "answer": "Based on our previous discussion..."
}
```

### `GET /`
Health check endpoint.

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OPENAI_API_KEY` | Yes | - | OpenAI API key |
| `PORT` | No | 8000 | Server port |
| `ALLOWED_ORIGINS` | No | * | CORS allowed origins (comma-separated) |
| `MAX_FILE_SIZE_MB` | No | 10 | Max upload size in MB |

## Deployment to GCP

### Cloud Run

1. **Build and push to Artifact Registry:**
```bash
gcloud builds submit --tag gcr.io/PROJECT_ID/rag-chatbot
```

2. **Deploy to Cloud Run:**
```bash
gcloud run deploy rag-chatbot \
  --image gcr.io/PROJECT_ID/rag-chatbot \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars OPENAI_API_KEY=sk-your-key-here
```

### Compute Engine / GKE

Use the provided `Dockerfile` with your orchestration tool of choice.

## Production Considerations

⚠️ **Current limitations:**
- Session storage is in-memory (resets on restart)
- No rate limiting
- No authentication/authorization

**Recommended improvements:**
- Use Redis or Cloud Firestore for session persistence
- Add API key authentication
- Implement rate limiting (e.g., slowapi)
- Add structured logging for Cloud Logging
- Store FAISS indices in Cloud Storage for persistence

## Architecture

```
User → FastAPI → LangChain → OpenAI Embeddings → FAISS
                     ↓
              ConversationalRetrievalChain
                     ↓
                 ChatGPT (gpt-4o-mini)
```

## License

MIT

