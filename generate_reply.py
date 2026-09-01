import os
import chromadb
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

client_db = chromadb.PersistentClient(path="./chroma_db")
collection = client_db.get_or_create_collection(name="friend_messages")

groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

def get_similar_messages(query_text, n_results=8):
    results = collection.query(
        query_texts=[query_text],
        n_results=n_results,
    )

    return results["documents"][0]

def build_prompt(query_text, similar_messages):
    examples_block = "\n".join(f"- {msg}" for msg in similar_messages)

    system_prompt = f"""You are imitating a specific person's texting style based on real examples of things they've said.

Here are real messages this person has sent in similar contexts:
{examples_block}

Study their tone, slang, punctuation habits, and message length. Respond to the next message the way THIS PERSON would respond — not generically, not like a helpful assistant. Keep responses short and casual like real Discord messages, matching their typical style. And avoid using emojis."""

    return system_prompt

def generate_response(query_text):
    similar = get_similar_messages(query_text)
    system_prompt = build_prompt(query_text, similar)

    completion = groq_client.chat.completions.create(
        model="openai/gpt-oss-120b",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": query_text},
        ],
        temperature=0.9,
        max_tokens=500,
    )

    return completion.choices[0].message.content

if __name__ == "__main__":
    test_input = input("Say something to the bot: ")
    reply = generate_response(test_input)
    print(f"\nBot reply: {reply}")