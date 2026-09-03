import os
import json
import uuid
import discord
import chromadb
import re
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
TRAINING_CHANNEL_ID = int(os.getenv("TRAINING_CHANNEL_ID", "0"))

TRAINING_MODE = True

HISTORY_FILE = "conversation_history.json"
MAX_HISTORY_MESSAGES = 10

# Chroma setup
client_db = chromadb.PersistentClient(path="./chroma_db")
collection = client_db.get_or_create_collection(name="freind_messages")
client_db = chromadb.PersistentClient(path="./chroma_db")
archive_collection = client_db.get_or_create_collection(name="server_archive")
collection = client_db.get_or_create_collection(name="friend_messages")
print(f"[debug] bot.py collection count: {collection.count()}")

# groq api keys setup
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# Dihcord setup
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.reactions = True
discord_client = discord.Client(intents=intents)

message_to_doc_id = {}

def load_history():
    # loads conversation history
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_history(history):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)

conversation_history = load_history()

def get_similar_messages(query_text, n_results=8):
    results = collection.query(query_texts=[query_text], n_results=n_results)
    return results["documents"][0]

def build_system_prompt(similar_messages):
    examples_block = "\n".join(f"- {msg}" for msg in similar_messages)
    return f"""You are imitating a specific person's texting style based on real examples of things they've said.

Here are real messages this person has sent in similar contexts:
{examples_block}

Study their tone, slang, punctuation habits, and message length. Respond the way THIS PERSON would respond — not generically, not like a helpful assistant. Keep responses short and casual like real Discord messages, matching their typical style. Stay consistent with the ongoing conversation. Do not use emojis."""

def add_message_to_db(text, source="generated", quality=0.5):
    doc_id = str(uuid.uuid4())
    collection.add(
        ids=[str(uuid.uuid4)],
        documents=[text],
        metadatas=[{"source": source, "quality": quality}],
    )
    return doc_id

def generate_response(conversation_id, user_message):
    similar = get_similar_messages(user_message)
    system_prompt = build_system_prompt(similar)

    if conversation_id not in conversation_history:
        conversation_history[conversation_id] = []

    history = conversation_history[conversation_id]

    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(history)
    messages.append({"role": "user", "content": user_message})

    print(f"[debug] querying with: '{user_message}'")
    similar = get_similar_messages(user_message)
    print(f"[debug] retrieved examples: {similar}")

    completion = groq_client.chat.completions.create(
        model="qwen/qwen3.8-27b",
        messages=messages,
        temperature=0.9,
        max_tokens=900,
    )

    reply = completion.choices[0].message.content

    if not reply or not reply.strip():
        reply = "..."

    history.append({"role": "user", "content": user_message})
    history.append({"role": "assistant", "content": reply})

    if len(history) > MAX_HISTORY_MESSAGES:
        conversation_history[conversation_id] = history[-MAX_HISTORY_MESSAGES:]

    save_history(conversation_history)

    doc_id = None
    if reply != "..." and len(reply.strip()) > 3:
        doc_id = add_message_to_db(reply, source="generated", quality=0.5)

    return reply, doc_id

def add_to_archive(text, author, channel_name, timestamp):
    doc_id = str(uuid.uuid4())
    archive_collection.add(
        ids=[doc_id],
        documents=[text],
        metadatas=[{
            "author": author,
            "channel": channel_name,
            "timestamp": timestamp,
        }],
    )
    return doc_id

def search_archive(query_text, n_results=5):
    results = archive_collection.query(query_texts=[query_text], n_results=n_results)
    documents = results["documents"][0]
    metadatas = results["metadatas"][0]
    return list(zip(documents, metadatas))

@discord_client.event
async def on_ready():
    mode = "TRAINING (single channel only)" if TRAINING_MODE else "LIVE ALL CHANNELS (mention-based)"
    print(f"Logged in as {discord_client.user}")
    print(f"Mode: {mode}")

@discord_client.event
async def on_message(message):
    if message.author.bot:
        return

    in_training_channel = message.channel.id == TRAINING_CHANNEL_ID
    is_mentioned = discord_client.user in message.mentions

    if message.content.startswith("!remember "):
        note = message.content[len("!remember"):].strip()
        add_to_archive(
            text=note,
            author=str(message.author),
            channel_name=message.channel.name,
            timestamp=message.created_at.isoformat(),
        )
        await message.channel.send(f"Message archived: \"{note}\"")
        return

    if message.content.startswith("!recall "):
        query = message.content[len("!recall "):].strip()
        results = search_archive(query)

        if not results:
            await message.channel.send("Nothing found in the archive")
        else:
            response_lines = ["**Found these:**"]
            for text, meta in results:
                response_lines.append(f"- \"{text}\" - {meta['author']} in #{meta['channel']}")
            await message.channel.send("\n".join(response_lines))
        return

    if TRAINING_MODE:
        if not in_training_channel:
            return
    else:
        if not is_mentioned:
            return

    cleaned_content = re.sub(r'<@[!&]?\d+>', '', message.content).strip()

    cleaned_content = (
        message.content
        .replace(f"<@{discord_client.user.id}>", "")
        .replace(f"<@!{discord_client.user.id}>", "")
        .strip()
    )


    async with message.channel.typing():
        conversation_id = str(message.channel.id)
        reply, doc_id = generate_response(conversation_id, cleaned_content)

    sent_message = await message.channel.send(reply)

    if doc_id is not None:
        message_to_doc_id[sent_message.id] = doc_id

@discord_client.event
async def on_raw_reaction_add(payload):
    if payload.user_id == discord_client.user.id:
        return

    if payload.message_id not in message_to_doc_id:
        return

    doc_id = message_to_doc_id[payload.message_id]
    emoji = str(payload.emoji)

    if emoji == "👍":
        collection.update(
            ids=[doc_id],
            metadatas=[{"source": "generated", "quality": 1.0}],
        )
        print(f"[feedback] 👍 on doc {doc_id} - quality boosted")

    elif emoji == "👎":
        collection.delete(ids=[doc_id])

        del message_to_doc_id[payload.message_id]
        print(f"[feedback] 👎 on doc {doc_id} - deleted from DB")
    elif emoji == "📌":
        channel = discord_client.get_channel(payload.channel_id)
        message = await channel.fetch_message(payload.message_id)

        add_to_archive(
            text=message.content,
            author=str(message.author),
            channel_name=channel.name,
            timestamp=message.created_at.isoformat(),
        )
        print(f"[archive] Saved message from {message.author}: {message.content[:50]}")


if __name__ == "__main__":
    if not DISCORD_TOKEN:
        raise SystemExit("Missing DISCORD_TOKEN in .env")
    discord_client.run(DISCORD_TOKEN)