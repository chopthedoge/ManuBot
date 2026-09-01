import os
import json
import threading
import msvcrt
import discord
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
TARGET_USER_ID = int(os.getenv("TARGET_USER_ID", "0"))
GUILD_ID = int(os.getenv("GUILD_ID", "0"))
OUTPUT_FILE = "friend_messages.json"

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

client = discord.Client(intents=intents)

collected = []

stop_requested = False

def listen_for_escape():
    global stop_requested
    while not stop_requested:
        if msvcrt.kbhit():
            key = msvcrt.getch()

            if key == b'\x1b':
                print("\nEscape pressed - stopping after current message")
                stop_requested = True

@client.event
async def on_ready():
    print(f"Logged in as {client.user}")
    print(f"Press ESC at any time to stop early and save what's been collected")

    listener_thread = threading.Thread(target=listen_for_escape, daemon=True)
    listener_thread.start()

    guild = client.get_guild(GUILD_ID)
    if guild is None:
        print(f"Could not find guild with ID {GUILD_ID}. Check the ID")
        await client.close()
        return

    print(f"Scraping guild: {guild.name}")

    for channel in guild.text_channels:
        if stop_requested:
            break

        perms = channel.permissions_for(guild.me)
        if not perms.read_message_history:
            print(f"Skipping #{channel.name} (no read history permission granted)")
            continue

        print(f"Scanning #{channel.name}...")
        count_in_channel = 0

        try:
            async for message in channel.history(limit=None, oldest_first=True):
                if stop_requested:
                    break

                if message.author.id == TARGET_USER_ID and message.content.strip():
                    collected.append({
                        "id": str(message.id),
                        "channel": channel.name,
                        "content": message.content,
                        "timestamp": message.created_at.isoformat(),
                        "reply_to": (
                            message.reference.message_id
                            if message.reference else None
                        ),
                    })
                    count_in_channel += 1
        except discord.Forbidden:
            print(f"   No access to #{channel.name}, skipping")
            continue
        except Exception as e:
            print(f"  Error in #{channel.name}: {e}")
            continue

        print(f"   -> {count_in_channel} messages collected from #{channel.name}")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(collected, f, indent=2, ensure_ascii=False)

    status = "Stopped early" if stop_requested else "Done"
    print(f"\n{status}. {len(collected)} total messages saved to {OUTPUT_FILE}")
    await client.close() 

if __name__ == "__main__":
    if not DISCORD_TOKEN:
        raise SystemExit("Missing DISCORD_TOKEN in .env")
    if TARGET_USER_ID == 0 or GUILD_ID == 0:
        raise SystemExit("Set TARGET_USER_ID and GUILD_ID in .env before running")

    client.run(DISCORD_TOKEN)