import json
import chromadb

client = chromadb.PersistentClient(path="./chroma_db")

collection = client.get_or_create_collection(name="friend_messages")

with open("friend_messages.json", "r", encoding="utf-8") as f:
    messages = json.load(f)

print(f"Loaded {len(messages)} messages from JSON")

ids = []
documents = []
metadatas = []

for msg in messages:
    ids.append(msg["id"])
    documents.append(msg["content"])
    metadatas.append({
        "channel": msg["channel"],
        "timestamp": msg["timestamp"],
        "source": "original",
        "quality": 1.0,
    })

BATCH_SIZE = 500

for i in range(0, len(ids), BATCH_SIZE):
    batch_ids = ids[i:i+BATCH_SIZE]
    batch_docs = documents[i:i+BATCH_SIZE]
    batch_meta = metadatas[i:i+BATCH_SIZE]

    collection.add(
        ids=batch_ids,
        documents=batch_docs,
        metadatas=batch_meta,
    )
    print(f"Added batch {i} to {i+len(batch_ids)}")

print(f"\nDone. Collection now has {collection.count()} messages stored")