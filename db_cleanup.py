import chromadb

client_db = chromadb.PersistentClient(path="./chroma_db")
collection = client_db.get_or_create_collection(name="friend_messages")

# fetch all entries with source == "generated"
results = collection.get(where={"source": "generated"})
bad_ids = results["ids"]

if bad_ids:
    collection.delete(ids=bad_ids)
    print(f"Deleted {len(bad_ids)} generated entries")
else:
    print("Nothing to delete")