import discord
from discord.ext import commands
from discord.ext.commands import check
from cogs.storage import get_log_channel_id, set_log_channel_id
import yt_dlp as youtube_dl
import os
import asyncio
import time
import uuid
import json

CONFIG_FILE = "allowed_channels.json" 

# Utility to check if a string is a URL
def is_url(string):
    return string.startswith("http://") or string.startswith("https://")

def in_music_channel():
    def predicate(ctx):
        cog = ctx.bot.get_cog("Voice")
        if not cog:
            return False

        guild_id = str(ctx.guild.id)
        if guild_id not in cog.allowed_channels:
            return False

        return ctx.channel.id == cog.allowed_channels[guild_id]
    return check(predicate)

#  sends logs to Discord channel and terminal
async def log_to_channel(client, guild, message, author_name=None):
    log_channel_id = get_log_channel_id(guild.id)
    log_channel = guild.get_channel(log_channel_id)

    # Construct the message with or without author_name
    if author_name:
        formatted_message = f"{message} by User: **{author_name}**"
    else:
        formatted_message = message

    # Send to Discord log channel if it exists
    if log_channel:
        await log_channel.send(formatted_message)

    # Print to terminal with server name
    if author_name:
        print(f"{formatted_message} in Server: **{guild.name}**")
    else:
        print(f"{message} in Server: **{guild.name}**")


class Voice(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.song_queue = asyncio.Queue()  # Queue to manage songs
        self.current_song = None
        self.audio_player_task = bot.loop.create_task(self.audio_player())  # Start the audio player loop
        self.timeout_duration = 180  # time duration default 3 minutes
        self.last_activity = time.time()
        self.inactivity_check_task = bot.loop.create_task(self.inactivity_check())
        self.temp_dir = "temp_music"
        os.makedirs(self.temp_dir, exist_ok=True)
        self.cache = {}
        self.preloaded_songs = {}  # url: (title, filepath, ctx)
        self.preloader_task = bot.loop.create_task(self.preload_songs())
        self.allowed_channels = self.load_allowed_channels()


    def load_allowed_channels(self):
        try:
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def save_allowed_channels(self):
        with open(CONFIG_FILE, "w") as f:
            json.dump(self.allowed_channels, f, indent=4)


    # Runs the blocking yt_dlp download in a separate thread to avoid freezing the event loop
    async def download_song(self, url):
        # Return cached file if already downloaded
        if url in self.cache and os.path.exists(self.cache[url]):
            return self.cache[url]

        unique_id = str(uuid.uuid4())
        filename_no_ext = os.path.join(self.temp_dir, f"song_{unique_id}") # Save with "song" as base filename
        final_filename = f"{filename_no_ext}.mp3"
        
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': f'{filename_no_ext}.%(ext)s',  
            'default_search': 'ytsearch',  # Allow search terms
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'quiet': True,  # Suppress verbose logging
        }

        def run_ydl():
            with youtube_dl.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])

        # Offload blocking work to thread
        await asyncio.to_thread(run_ydl)

        # Save in cache
        self.cache[url] = final_filename
        return final_filename

    # Audio playback loop: handles queueing, downloading, and playing songs
    async def audio_player(self):
        while True:
            try:
                self.current_song = await asyncio.wait_for(self.song_queue.get(), timeout=self.timeout_duration)  # Wait for the next song in the queue
                title, url, ctx = self.current_song

                # Connect to voice channel if not already connected or gives error if user who issued
                # command is not in a voice channel
                voice = ctx.voice_client
                if not voice:
                    if ctx.author.voice and ctx.author.voice.channel:
                        voice = await ctx.author.voice.channel.connect()
                    else:
                        await ctx.send("❌ You need to be in a voice channel to play music.")
                        continue



                # Download the song and get its filename
                try:
                    if url in self.preloaded_songs:
                        title, filename, ctx = self.preloaded_songs.pop(url)
                    else:
                        try:
                            filename = await self.download_song(url)
                        except Exception as e:
                            await ctx.send(f"Error downloading: {e}")
                            continue

                except Exception as e:
                    await ctx.send(f"Error downloading: {e}")
                    continue

                # Play the song
                voice.play(discord.FFmpegPCMAudio(filename), after=lambda e: print("Playback finished."))
                message = await ctx.send(f"🔊 **Now Playing:** [{title}]({url})", suppress_embeds=True)


                # Wait until the song is done before starting the next one
                while voice.is_playing():
                    await asyncio.sleep(1)
    
                self.current_song = None

                # Clean up only if it's not cached
                if url not in self.cache or self.cache[url] != filename:
                    if os.path.exists(filename):
                        os.remove(filename)

            except asyncio.TimeoutError:
                self.current_song = None
                for vc in self.bot.voice_clients:
                    if vc.is_connected():
                        await vc.disconnect()
                        print("Disconnected due to queue inactivity timeout.")
                        self.cache.clear()
                continue  # Stop the audio player loop

    async def preload_songs(self):
        while True:
            await asyncio.sleep(1)

            # Look ahead into the queue
            queue_list = list(self.song_queue._queue)
            for title, url, ctx in queue_list:
                if url not in self.preloaded_songs:
                    try:
                        filename = await self.download_song(url)
                        self.preloaded_songs[url] = (title, filename, ctx)
                    except Exception as e:
                        print(f"Preload error for {url}: {e}")

    async def inactivity_check(self):
        check_interval = 30  # How often to check for inactivity (in seconds)
        inactivity_timer = 0

        while True:
            await asyncio.sleep(check_interval)

            for guild in self.bot.guilds:
                voice_client = guild.voice_client
                if voice_client and voice_client.is_connected():
                    channel = voice_client.channel
                    members = [m for m in channel.members if not m.bot]

                    is_alone = len(members) == 0

                    # Track idle time per guild using a custom attribute
                    if not hasattr(voice_client, "inactivity_timer"):
                        voice_client.inactivity_timer = 0

                    if is_alone:
                        voice_client.inactivity_timer += check_interval
                    else:
                        voice_client.inactivity_timer = 0

                    if voice_client.inactivity_timer >= self.timeout_duration:
                        await voice_client.disconnect()
                        print(f"Disconnected from {channel.name} due to reaching inactivity timer while alone.")
                        voice_client.inactivity_timer = 0  # Reset
                        self.cache.clear()


    @commands.command()
    @in_music_channel()
    async def play(self, ctx, *, search: str):
        if not ctx.author.voice or not ctx.author.voice.channel:
            await ctx.send("❌ You need to be in a voice channel to use this command.")
            return

        # Adds a song to the queue, by URL or search term.
        query = search if is_url(search) else f"ytsearch:{search}"

        ydl_opts = {
            'format': 'bestaudio/best',
            'quiet': True,
            'default_search': 'ytsearch',
        }

        try:
            def get_info():
                with youtube_dl.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(query, download=False)
                    if 'entries' in info:
                        # Playlist: return all entries
                        return [(entry['title'], entry['webpage_url']) for entry in info['entries']]
                    else:
                        # Single video
                        return [(info['title'], info['webpage_url'])]


            songs = await asyncio.to_thread(get_info)

            for title, url in songs:
                await self.song_queue.put((title, url, ctx))
                msg = await ctx.send(f"🎶 **Queued:** [{title}]({url})", suppress_embeds=True)
                #print(f"Song queued: {title} ({url}) by {ctx.author.name} in {ctx.guild.name}") # Log the song being queued
                await log_to_channel(self.bot, ctx.guild, f"**Added to Queue:** [{title}]({url})", author_name=ctx.author.name)



            
            if len(songs) > 1:
                await ctx.send(f"✅ **Added `{len(songs)}` tracks to the queue.**")
                await log_to_channel(self.bot, ctx.guild, f"✅ **Added `{len(songs)}` tracks to the queue.**", author_name=ctx.author.name)
                #print(f"✅ Added {len(songs)} tracks to the queue.")

        except Exception as e:
            await ctx.send(f"❌ **Error retrieving song: {e}**")
            await log_to_channel(self.bot, ctx.guild, f"**Error retrieving song: {e}**", author_name=ctx.author.name)
            #print(f"❌ Error retrieving song: {e}")

    @commands.command()
    @in_music_channel()
    async def now(self, ctx):
        if self.current_song:
            title, url, _ = self.current_song
            msg = await ctx.send(f"🎧 **Now Playing: [{title}]({url})**", suppress_embeds=True)

            # Log to Discord and terminal
            await log_to_channel(self.bot, ctx.guild, f"**Now Playing: [{title}]({url})**", author_name=ctx.author.name)
            #print(f"🎧 Now Playing: {title} ({url})")
        else:
            await ctx.send("Nothing is playing right now.")

    @commands.command()
    @in_music_channel()
    async def skip(self, ctx): # Skips the current song. 
        voice = ctx.voice_client
        if voice and voice.is_playing():
            voice.stop()
            self.preloaded_songs.clear()
            self.current_song = None
            await ctx.send("⏩ **Skipped the current song.**")

            # Log to Discord and terminal
            await log_to_channel(self.bot, ctx.guild, "**Skipped the current song.**", author_name=ctx.author.name)
            #print("⏩ Skipped the current song.")

    @commands.command()
    @in_music_channel()
    async def queue(self, ctx): # Displays the currently playing song and queue. 
        if self.song_queue.empty() and not self.current_song:
            await ctx.send("Queue is empty.")
        else:
            lines = []

            if self.current_song:
                title, url, _ = self.current_song
                lines.append(f"🎧 **Now Playing:** [{title}]({url})")

            queue_list = list(self.song_queue._queue)
            if queue_list:
                lines.append("\n**Up Next:**")
                lines += [f"{i+1}. [{song[0]}]({song[1]})" for i, song in enumerate(queue_list)]

            await ctx.send("\n".join(lines), suppress_embeds=True)

            # Log to Discord and terminal
            await log_to_channel(self.bot, ctx.guild, "**Showing Queue**", author_name=ctx.author.name)
            #print("📜 Showing Queue")

    @commands.command()
    @in_music_channel()
    async def stop(self, ctx): # Stops playback and clears the queue.""      
        voice = ctx.voice_client
        if voice and voice.is_playing():
            voice.stop()

        # Clear queue
        while True:
            try:
                self.song_queue.get_nowait()
            except asyncio.QueueEmpty:
                break

        await ctx.send("**Stopped playback and cleared queue.**")

        # Log to Discord and terminal
        await log_to_channel(self.bot, ctx.guild, "**Stopped playback and cleared queue.**", author_name=ctx.author.name)
        #print("Stopped playback and cleared queue.")


    @commands.command()
    @in_music_channel()
    async def leave(self, ctx):    
        voice = ctx.voice_client
        if voice and voice.is_connected():
            await voice.disconnect()
            self.preloaded_songs.clear()
            self.current_song = None
            self.cache.clear()

            removed = 0
            for file in os.listdir(self.temp_dir):
                if file.endswith(".mp3"):
                    os.remove(os.path.join(self.temp_dir, file))
                    removed += 1

            #displays to user
            await ctx.send(f"👋 **Left the voice channel.**")

            # Log to Discord and terminal
            await log_to_channel(self.bot, ctx.guild, f"**Left the voice channel via !leave. Removed {removed} temp files and cleared cache.**", author_name=ctx.author.name)
            #print("👋 Left the voice channel.")

    @commands.command()
    @in_music_channel()
    async def ping(self, ctx):
        latency = round(self.bot.latency * 1000)
        await ctx.send(f"**Ping:`{latency}ms`**")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def clearcache(self, ctx):
        self.cache.clear()
        removed = 0
        for file in os.listdir(self.temp_dir):
            if file.endswith(".mp3"):
                os.remove(os.path.join(self.temp_dir, file))
                removed += 1
        await ctx.send(f"**🧹 Cleared cache and removed {removed} temp files.**")
        self.preloaded_songs.clear()

    @commands.command(name="setrequestchannel")
    @commands.has_permissions(administrator=True)
    async def set_request_channel(self, ctx):
        guild_id = str(ctx.guild.id)
        self.allowed_channels[guild_id] = ctx.channel.id
        self.save_allowed_channels()
        await ctx.send(f"✅ This channel (`{ctx.channel.name}`) is now the music request channel.")

        # Log to Discord and terminal
        await log_to_channel(self.bot, ctx.guild, f"✅ Set request channel to {ctx.channel.name}.", author_name=ctx.author.name)
        print(f"✅ Set request channel to {ctx.channel.name}.")



# Required setup function to add this cog to the bot
async def setup(bot):
    await bot.add_cog(Voice(bot))
