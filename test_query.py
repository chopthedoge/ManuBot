import chromadb

client_db = chromadb.PersistentClient(path="./chroma_db")
collection = client_db.get_or_create_collection(name="friend_messages")

results1 = collection.query(query_texts=["hello how are you"], n_results=5)
print("Query 1:", results1["documents"][0])

results2 = collection.query(query_texts=["what is your favorite video game"], n_results=5)
print("Query 2:", results2["documents"][0])