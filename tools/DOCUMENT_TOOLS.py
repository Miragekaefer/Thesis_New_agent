import json
import math
import ollama

from tools.HELPERS import ok, ask

# Embedding model used when creating knowledge.json
EMBED_MODEL = "nomic-embed-text"

KNOWLEDGE_FILE = "knowledge.json"


def cosine_similarity(vec1, vec2):
    """
    Calculate cosine similarity between two embeddings.
    Returns a value between -1 and 1.
    Higher = more similar.
    """

    dot_product = sum(a * b for a, b in zip(vec1, vec2))

    magnitude1 = math.sqrt(sum(a * a for a in vec1))
    magnitude2 = math.sqrt(sum(b * b for b in vec2))

    if magnitude1 == 0 or magnitude2 == 0:
        return 0

    return dot_product / (magnitude1 * magnitude2)


def search_documents_tool(input_data):
    """
    Search the embedded PDF knowledge base using semantic search.
    """

    query = input_data.get("query")

    if not query:
        return ask(
            "What would you like me to search for?",
            missing_fields=["query"]
        )

    # -----------------------------------------
    # Load stored knowledge
    # -----------------------------------------

    try:
        with open(KNOWLEDGE_FILE, "r", encoding="utf-8") as f:
            knowledge = json.load(f)

    except FileNotFoundError:
        return ok(
            data=[],
            message="Knowledge base has not been created yet."
        )

    # -----------------------------------------
    # Create embedding for the user's question
    # -----------------------------------------

    response = ollama.embed(
        model=EMBED_MODEL,
        input=query
    )

    query_embedding = response["embeddings"][0]

    # -----------------------------------------
    # Compare against every document chunk
    # -----------------------------------------

    results = []

    for chunk in knowledge:

        similarity = cosine_similarity(
            query_embedding,
            chunk["embedding"]
        )

        results.append({
            "text": chunk["text"],
            "similarity": similarity
        })

    # -----------------------------------------
    # Sort by similarity
    # -----------------------------------------

    results.sort(
        key=lambda x: x["similarity"],
        reverse=True
    )

    # Keep only the 5 best matches
    best_matches = results[:5]

    return ok(
        data={
            "documents": best_matches
        },
        message=f"Found {len(best_matches)} relevant document sections."
    )


DOCUMENT_TOOLS = {

    "search_documents": search_documents_tool,

}