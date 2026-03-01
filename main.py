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
intents.members = True

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


@tree.command(name="play", description="Odtwarza piosenkę lub dodaje do kolejki")
@app_commands.describe(query="Nazwa / link YouTube / Spotify itd.")
async def play(interaction: discord.Interaction, query: str):
    if not interaction.user.voice:
        return await interaction.response.send_message("Musisz być na kanale głosowym!", ephemeral=True)

    channel = interaction.user.voice.channel

    if not interaction.guild.voice_client:
        vc = await channel.connect()
    else:
        vc = interaction.guild.voice_client

    await interaction.response.defer()

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(query, download=False)
            if "entries" in info:  # playlist
                entries = info["entries"][:10]  # max 10 z playlisty
            else:
                entries = [info]
        except:
            # wyszukiwanie
            search = ydl.extract_info(f"ytsearch:{query}", download=False)
            entries = [search["entries"][0]] if search.get("entries") else []

    if not entries:
        return await interaction.followup.send("Nic nie znaleziono... 😔")

    if interaction.guild.id not in queues:
        queues[interaction.guild.id] = deque()

    added_count = 0
    for entry in entries:
        queues[interaction.guild.id].append({
            "url": entry["url"],
            "title": entry["title"],
            "channel": interaction.channel
        })
        added_count += 1

    msg = f"Dodałem **{added_count}** utwór(ów) do kolejki!"
    if not vc.is_playing() and not vc.is_paused():
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


bot.run(TOKEN)