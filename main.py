import discord
from discord import app_commands
from discord.ext import commands
import yt_dlp
import asyncio
from collections import deque
import os
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")          # albo wklej na sztywno (nie polecam)

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
intents.members = False

bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

# Kolejka na serwer (guild)
queues = {}           # guild_id -> deque[dict]

ydl_opts = {
    "format": "bestaudio/best",
    "noplaylist": True,
    "quiet": True,
    "default_search": "ytsearch",
    "extract_flat": True,
}


async def play_next(guild: discord.Guild):
    if guild.id not in queues or not queues[guild.id]:
        return

    vc = guild.voice_client
    if not vc or not vc.is_connected():
        return

    song = queues[guild.id].popleft()
    url = song["url"]
    title = song["title"]

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            real_url = info["url"]

        vc.play(
            discord.FFmpegPCMAudio(
                real_url,
                executable="ffmpeg",
                before_options="-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
                options="-vn"
            ),
            after=lambda e: asyncio.run_coroutine_threadsafe(play_next(guild), bot.loop)
        )

        channel = song.get("channel")
        if channel:
            await channel.send(f"Teraz gram → **{title}**")

    except Exception as e:
        print(f"Błąd odtwarzania: {e}")
        await play_next(guild)


@bot.event
async def on_ready():
    print(f"Zalogowano jako {bot.user}")
    try:
        synced = await tree.sync()
        print(f"Zsynchronizowano {len(synced)} komend slash")
    except Exception as e:
        print(e)


@tree.command(name="play", description="Odtwarza utwór / dodaje do kolejki")
@app_commands.describe(query="Nazwa / link YouTube")
async def play(interaction: discord.Interaction, query: str):
    if not interaction.user.voice:
        return await interaction.response.send_message("Musisz być na kanale głosowym!", ephemeral=True)

    channel = interaction.user.voice.channel
    vc = interaction.guild.voice_client or await channel.connect()

    await interaction.response.defer()

    entries = []
    error_msg = None

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(query, download=False)
            if "entries" in info:
                entries = info["entries"][:10]  # playlist lub wyszukiwanie
            else:
                entries = [info]  # pojedynczy link
        except Exception as e:
            error_msg = f"Błąd yt-dlp: {str(e)[:100]}..."
            print(f"yt-dlp error: {e}")

    if not entries:
        # Druga próba – czysta wyszukiwanie
        try:
            search = ydl.extract_info(f"ytsearch5:{query}", download=False)  # ytsearch5 = max 5 wyników
            entries = search.get("entries", [])[:5]
        except Exception as e:
            print(f"Search fallback error: {e}")

    if not entries:
        msg = "Nic nie znaleziono 😔" 
        if error_msg:
            msg += f"\n({error_msg})"
        return await interaction.followup.send(msg)

    if interaction.guild.id not in queues:
        queues[interaction.guild.id] = deque()

    added = 0
    for entry in entries:
        # Bezpieczne pobranie – jeśli brak klucza, pomijamy lub fallback
        url = entry.get("url") or entry.get("webpage_url") or entry.get("id")
        title = entry.get("title") or entry.get("fulltitle") or "??? (brak tytułu)"

        if not url:
            continue  # pomijamy bezsensowne entry

        queues[interaction.guild.id].append({
            "url": url,
            "title": title,
            "channel": interaction.channel
        })
        added += 1

    msg = f"Dodałem **{added}** utwór(ów) do kolejki!"
    if added == 0:
        msg = "Żaden utwór nie został dodany (uszkodzone wyniki z YouTube 😢)"

    if not vc.is_playing() and not vc.is_paused() and added > 0:
        await play_next(interaction.guild)

    await interaction.followup.send(msg)


@tree.command(name="skip", description="Pomija aktualny utwór")
async def skip(interaction: discord.Interaction):
    vc = interaction.guild.voice_client
    if vc and vc.is_playing():
        vc.stop()
        await interaction.response.send_message("⏭ Pominięto!")
    else:
        await interaction.response.send_message("Nic nie gra...", ephemeral=True)


@tree.command(name="stop", description="Zatrzymuje i czyści kolejkę")
async def stop(interaction: discord.Interaction):
    vc = interaction.guild.voice_client
    if vc:
        queues.pop(interaction.guild.id, None)
        vc.stop()
        await vc.disconnect()
        await interaction.response.send_message("👋 Zatrzymano i wyszedłem z kanału.")
    else:
        await interaction.response.send_message("Nie jestem na kanale głosowym.")


@tree.command(name="queue", description="Pokazuje kolejkę")
async def queue_cmd(interaction: discord.Interaction):
    if interaction.guild.id not in queues or not queues[interaction.guild.id]:
        return await interaction.response.send_message("Kolejka jest pusta.", ephemeral=True)

    q = queues[interaction.guild.id]
    text = "\n".join([f"{i+1}. {s['title']}" for i, s in enumerate(q)])
    await interaction.response.send_message(f"**Kolejka ({len(q)}):**\n{text}", ephemeral=True)
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import os

class HealthCheck(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"OK")

def run_health_server():
    port = int(os.getenv("PORT", 10000))  # Render wymaga PORT
    server = HTTPServer(("", port), HealthCheck)
    server.serve_forever()

if __name__ == "__main__":
    threading.Thread(target=run_health_server, daemon=True).start()
    bot.run(os.getenv("DISCORD_TOKEN"))


bot.run(TOKEN)


