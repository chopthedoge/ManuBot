import chromadb

client_db = chromadb.PersistentClient(path="./chroma_db")
collection = client_db.get_or_create_collection(name="friend_messages")

print(f"Total documents in collection: {collection.count()}")

# peek at a random sample
sample = collection.peek(limit=10)
print(sample["documents"])