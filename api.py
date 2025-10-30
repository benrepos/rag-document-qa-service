from typing import Dict, Any, Optional
import io
import os
import logging

# Configure logging FIRST (before any imports that use logging)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, validator
from PyPDF2 import PdfReader
from PyPDF2.errors import PdfReadError
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from utils.text_splitter import split_text
from utils.firestore_storage import (
    create_conversation,
    save_message,
    get_conversation_history,
    get_user_conversations,
)
from agent.langchain_agent import (
    build_faiss_index,
    run_qa,
    create_conversational_chain,
)

# Validate OpenAI API key is set
if not os.getenv("OPENAI_API_KEY"):
    raise RuntimeError("OPENAI_API_KEY environment variable is not set")

# Rate limiter
limiter = Limiter(key_func=get_remote_address)

app = FastAPI(title="RAG Chatbot API")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS middleware for web frontends
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", "10"))
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024

# In-memory session store. For production, use a persistent store.
user_sessions: Dict[str, Dict[str, Any]] = {}


class AskRequest(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=100, pattern="^[a-zA-Z0-9_-]+$")
    question: str = Field(..., min_length=1, max_length=2000)


class ChatRequest(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=100, pattern="^[a-zA-Z0-9_-]+$")
    message: str = Field(..., min_length=1, max_length=2000)


class QAResponse(BaseModel):
    answer: str


def _extract_text_from_upload(upload: UploadFile) -> str:
    """Extract text from an uploaded file (PDF or text)."""
    if upload.content_type == "application/pdf":
        try:
            data = upload.file.read()
            reader = PdfReader(io.BytesIO(data))
            return "\n".join([(page.extract_text() or "") for page in reader.pages])
        except (PdfReadError, ValueError) as e:
            logger.warning(f"PDF parsing failed: {e}")
            raise HTTPException(status_code=400, detail=f"PDF parsing failed: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error parsing PDF: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Internal server error processing PDF")
    # Fallback: treat as utf-8 text
    try:
        return upload.file.read().decode("utf-8", errors="ignore")
    except Exception as e:
        logger.error(f"Error reading text file: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error reading file")


@app.post("/upload")
@limiter.limit("5/minute")
def upload_document(request: Request, user_id: str = Form(..., min_length=1, max_length=100, regex="^[a-zA-Z0-9_-]+$"), file: UploadFile = File(...)) -> dict:
    logger.info(f"Upload request from user_id={user_id}, filename={file.filename}")
    
    # Validate file size
    file.file.seek(0, 2)  # Seek to end
    file_size = file.file.tell()
    file.file.seek(0)  # Reset to start
    
    logger.info(f"File size: {file_size} bytes")
    
    if file_size > MAX_FILE_SIZE_BYTES:
        logger.warning(f"File too large: {file_size} bytes (max: {MAX_FILE_SIZE_BYTES})")
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size is {MAX_FILE_SIZE_MB}MB."
        )
    
    try:
        text = _extract_text_from_upload(file)
    finally:
        try:
            file.file.close()
        except Exception:
            pass

    if not text.strip():
        logger.warning(f"Empty text extracted from {file.filename}")
        raise HTTPException(status_code=400, detail="Could not extract text from file. If it's scanned, OCR is required.")

    chunks = split_text(text)
    logger.info(f"Split document into {len(chunks)} chunks")
    
    metadatas = [{"source": file.filename, "chunk_id": i} for i in range(len(chunks))]
    index = build_faiss_index(chunks, metadatas=metadatas)

    # Create conversation in Firestore
    conversation_id = create_conversation(user_id, file.filename)

    session = user_sessions.get(user_id) or {}
    session["faiss_index"] = index
    session["conversation_id"] = conversation_id
    session["document_name"] = file.filename
    # Reset any previous conversational chain/memory for this user
    session.pop("chain", None)
    session.pop("memory", None)
    user_sessions[user_id] = session
    
    logger.info(f"Successfully indexed document for user_id={user_id}, conversation_id={conversation_id}")
    return {"status": "ok", "chunks": len(chunks), "filename": file.filename, "conversation_id": conversation_id}


@app.post("/ask", response_model=QAResponse)
@limiter.limit("20/minute")
def ask(request: Request, req: AskRequest) -> QAResponse:
    logger.info(f"Ask request from user_id={req.user_id}")
    session = user_sessions.get(req.user_id)
    if not session or "faiss_index" not in session:
        logger.warning(f"No index found for user_id={req.user_id}")
        raise HTTPException(status_code=400, detail="No document indexed for this user. Upload first at /upload.")
    
    conversation_id = session.get("conversation_id")
    
    # Save user message
    save_message(conversation_id, "user", req.question)
    
    # Get answer
    answer = run_qa(session["faiss_index"], req.question)
    
    # Save assistant message
    save_message(conversation_id, "assistant", answer)
    
    logger.info(f"Answered question for user_id={req.user_id}")
    return QAResponse(answer=answer)


@app.post("/chat", response_model=QAResponse)
@limiter.limit("20/minute")
def chat(request: Request, req: ChatRequest) -> QAResponse:
    logger.info(f"Chat request from user_id={req.user_id}")
    session = user_sessions.get(req.user_id)
    if not session or "faiss_index" not in session:
        logger.warning(f"No index found for user_id={req.user_id}")
        raise HTTPException(status_code=400, detail="No document indexed for this user. Upload first at /upload.")

    conversation_id = session.get("conversation_id")
    
    # Save user message
    save_message(conversation_id, "user", req.message)

    # Build conversational chain once per user after index is ready
    if "chain" not in session or session["chain"] is None:
        logger.info(f"Creating conversational chain for user_id={req.user_id}")
        chain, memory = create_conversational_chain(session["faiss_index"])
        session["chain"], session["memory"] = chain, memory
        user_sessions[req.user_id] = session

    result = session["chain"]({"question": req.message})
    answer: Optional[str] = result.get("answer") or result.get("result")
    if not answer:
        answer = ""
    
    # Save assistant message with metadata
    save_message(
        conversation_id,
        "assistant",
        answer,
        metadata={
            "model": os.getenv("LLM_MODEL", "gpt-4o-mini"),
        }
    )
    
    logger.info(f"Answered chat message for user_id={req.user_id}")
    return QAResponse(answer=answer)


@app.get("/")
def health() -> dict:
    return {"status": "ok"}


@app.get("/conversations/{user_id}")
@limiter.limit("10/minute")
def list_conversations(request: Request, user_id: str):
    """List all conversations for a user."""
    logger.info(f"List conversations request for user_id={user_id}")
    conversations = get_user_conversations(user_id)
    return {"conversations": conversations}


@app.get("/conversations/{conversation_id}/messages")
@limiter.limit("10/minute")
def get_messages(request: Request, conversation_id: str):
    """Get all messages in a conversation."""
    logger.info(f"Get messages request for conversation_id={conversation_id}")
    messages = get_conversation_history(conversation_id)
    return {"messages": messages}


if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("PORT", "8000"))
    # For local dev only; production uses CMD in Dockerfile
    uvicorn.run("api:app", host="0.0.0.0", port=port, reload=True)


