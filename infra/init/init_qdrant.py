import os, time
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams

url = os.getenv("QDRANT_URL", "[qdrant](http://qdrant:6333)")
collection = os.getenv("QDRANT_COLLECTION", "chunks")

if __name__ == "__main__":
    client = QdrantClient(url=url)
    for _ in range(30):
        try:
            client.get_collections()
            break
        except Exception:
            time.sleep(2)
    if collection not in [c.name for c in client.get_collections().collections]:
        # placeholder dimensione vettore 1024; aggiorneremo quando scegliamo il modello embeddings
        client.create_collection(
            collection_name=collection,
            vectors_config=VectorParams(size=1024, distance=Distance.COSINE),
        )
        print(f"Created collection {collection}")
    else:
        print(f"Collection {collection} already exists")
