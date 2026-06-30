import os
import uuid
from typing import List
import chromadb
from chromadb.utils import embedding_functions
from app.config import config

# Ensure ChromaDB persist directory exists
os.makedirs(config.CHROMA_PERSIST_DIR, exist_ok=True)

# Initialize persistent ChromaDB client
client = chromadb.PersistentClient(path=config.CHROMA_PERSIST_DIR)

# Configure the local embeddings function
# ChromaDB will use sentence-transformers/all-MiniLM-L6-v2
embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name="all-MiniLM-L6-v2"
)

# Retrieve or create the user preferences collection
collection = client.get_or_create_collection(
    name="user_preferences",
    embedding_function=embedding_function
)

def store_memory(user_id: str, text: str) -> None:
    """Stores a piece of preference or fact in the user's vector memory.
    
    Args:
        user_id: The ID of the user (for metadata filtering).
        text: The content of the memory to store.
    """
    memory_id = f"{user_id}_{uuid.uuid4()}"
    collection.add(
        documents=[text],
        metadatas=[{"user_id": user_id}],
        ids=[memory_id]
    )

def retrieve_memories(user_id: str, query: str, k: int = 3) -> List[str]:
    """Retrieves the top k relevant memories for a user given a query.
    
    Args:
        user_id: The ID of the user.
        query: The search query.
        k: The number of memories to return.
        
    Returns:
        A list of retrieved memory strings.
    """
    try:
        results = collection.query(
            query_texts=[query],
            n_results=k,
            where={"user_id": user_id}
        )
        # Extract the documents matching the query (first query result)
        documents = results.get("documents", [])
        if documents and len(documents) > 0:
            return documents[0]
        return []
    except Exception:
        # Return empty list if collection is empty or query fails
        return []
