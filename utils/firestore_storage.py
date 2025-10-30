from google.cloud import firestore
from datetime import datetime, timedelta
from typing import Optional, List, Dict
import os
import logging

logger = logging.getLogger(__name__)

# Configuration
USE_FIRESTORE = os.getenv("USE_FIRESTORE", "false").lower() == "true"
print(f"USE_FIRESTORE: {USE_FIRESTORE}")

# Initialize Firestore client
if USE_FIRESTORE:
    try:
        db = firestore.Client()  # Uses (default) database
        logger.info("Firestore initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize Firestore: {e}")
        db = None
else:
    db = None
    logger.info("Firestore disabled (USE_FIRESTORE not set)")


def create_conversation(user_id: str, document_name: str) -> Optional[str]:
    """Create a new conversation and return its ID."""
    if not db:
        logger.debug("Firestore not initialized, skipping conversation creation")
        return None
    
    try:
        conv_ref = db.collection("conversations").document()
        conv_ref.set({
            "user_id": user_id,
            "document_name": document_name,
            "created_at": firestore.SERVER_TIMESTAMP,
            "updated_at": firestore.SERVER_TIMESTAMP,
            "expire_at": datetime.utcnow() + timedelta(days=90),  # Auto-delete after 90 days
        })
        logger.info(f"Created conversation {conv_ref.id} for user {user_id}")
        return conv_ref.id
    except Exception as e:
        logger.error(f"Failed to create conversation: {e}", exc_info=True)
        return None


def save_message(
    conversation_id: str,
    role: str,
    content: str,
    metadata: Optional[Dict] = None
) -> None:
    """Save a message to a conversation."""
    if not db or not conversation_id:
        return
    
    try:
        message_data = {
            "role": role,
            "content": content,
            "timestamp": firestore.SERVER_TIMESTAMP,
        }
        
        if metadata:
            message_data.update(metadata)
        
        # Add message to subcollection
        db.collection("conversations").document(conversation_id)\
          .collection("messages").add(message_data)
        
        # Update conversation timestamp
        db.collection("conversations").document(conversation_id).update({
            "updated_at": firestore.SERVER_TIMESTAMP
        })
        
        logger.debug(f"Saved {role} message to conversation {conversation_id}")
    except Exception as e:
        logger.error(f"Failed to save message: {e}", exc_info=True)


def get_conversation_history(conversation_id: str, limit: int = 50) -> List[Dict]:
    """Retrieve conversation history."""
    if not db or not conversation_id:
        return []
    
    try:
        messages_ref = db.collection("conversations").document(conversation_id)\
                         .collection("messages")\
                         .order_by("timestamp")\
                         .limit(limit)
        
        return [
            {**msg.to_dict(), "id": msg.id}
            for msg in messages_ref.stream()
        ]
    except Exception as e:
        logger.error(f"Failed to get conversation history: {e}", exc_info=True)
        return []


def get_user_conversations(user_id: str, limit: int = 20) -> List[Dict]:
    """Get all conversations for a user."""
    if not db:
        return []
    
    try:
        convs_ref = db.collection("conversations")\
                      .where("user_id", "==", user_id)\
                      .order_by("updated_at", direction=firestore.Query.DESCENDING)\
                      .limit(limit)
        
        return [
            {**conv.to_dict(), "id": conv.id}
            for conv in convs_ref.stream()
        ]
    except Exception as e:
        logger.error(f"Failed to get user conversations: {e}", exc_info=True)
        return []

