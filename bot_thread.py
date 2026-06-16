from dotenv import load_dotenv
load_dotenv()  # baca file .env

# ══════════════════════════════════════════════════════════════
# IMPORT LIBRARY
# Library = alat tambahan yang dipakai bot
# ══════════════════════════════════════════════════════════════
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import discord                  # library utama untuk bot Discord
from discord import app_commands # untuk bikin slash command (/)
from discord.ext import commands # untuk bikin bot nya
import asyncio                  # untuk fungsi tunggu/delay (asyncio.sleep)
import json                     # untuk simpan data ke file JSON
import os                       # untuk baca file & environment variable


# ══════════════════════════════════════════════════════════════
# SETUP BOT
# Intents = izin apa saja yang boleh dilakukan bot
# ══════════════════════════════════════════════════════════════
intents = discord.Intents.default()
intents.message_content = True  # izin baca isi pesan (wajib untuk auto-delete)
intents.messages = True         # izin pantau pesan masuk
intents.guilds = True           # izin akses server

bot = commands.Bot(command_prefix="!", intents=intents)


# ══════════════════════════════════════════════════════════════
# DATABASE SEDERHANA (JSON)
# Untuk menyimpan setting channel yang dipilih admin
# File thread_data.json akan dibuat otomatis di folder yang sama
# ══════════════════════════════════════════════════════════════
DB_PATH = os.path.join(os.path.dirname(__file__), "thread_data.json")

def load_db() -> dict:
    # Baca data dari file JSON
    # Kalau file belum ada, kembalikan dictionary kosong
    if not os.path.exists(DB_PATH):
        return {}
    with open(DB_PATH, "r") as f:
        return json.load(f)

def save_db(data: dict):
    # Simpan data ke file JSON
    with open(DB_PATH, "w") as f:
        json.dump(data, f, indent=2)

# Tambah sebelum ON_READY dan setelah Database
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'Bot is alive!')
    
    def log_message(self, format, *args):
        pass  # supaya tidak spam log

def run_server():
    server = HTTPServer(('0.0.0.0', 8080), Handler)
    server.serve_forever()

# ══════════════════════════════════════════════════════════════
# EVENT ON_READY
# Jalan otomatis saat bot pertama kali nyala
# ══════════════════════════════════════════════════════════════
@bot.event
async def on_ready():
    print(f"✅ Bot aktif sebagai {bot.user}")
    try:
        synced = await bot.tree.sync()  # daftarkan slash command ke Discord
        print(f"✅ Berhasil sync {len(synced)} slash command")
    except Exception as e:
        print(f"❌ Gagal sync command: {e}")


# ══════════════════════════════════════════════════════════════
# SLASH COMMAND /setchannel
# Dipakai admin untuk milih channel mana yang mau auto-thread
# Hanya admin (yang punya izin manage_guild) yang bisa pakai
# ══════════════════════════════════════════════════════════════
@bot.tree.command(name="setchannel", description="Set channel untuk auto-thread foto (khusus admin)")
@app_commands.checks.has_permissions(manage_guild=True)  # hanya admin
async def setchannel(interaction: discord.Interaction, channel: discord.TextChannel):
    # Simpan ID channel yang dipilih ke JSON
    db = load_db()
    db["thread_channel"] = channel.id
    save_db(db)

    await interaction.response.send_message(
        f"✅ Channel auto-thread berhasil diset ke {channel.mention}!\n"
        f"Sekarang hanya foto/video yang boleh dikirim di channel itu.",
        ephemeral=True  # pesan hanya keliatan sama admin yang ketik command
    )

# Kalau bukan admin yang pakai /setchannel, kasih pesan error
@setchannel.error
async def setchannel_error(interaction: discord.Interaction, error):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message(
            "❌ Kamu tidak punya izin untuk menggunakan command ini!",
            ephemeral=True
        )


# ══════════════════════════════════════════════════════════════
# SLASH COMMAND /ceksetting
# Untuk lihat channel mana yang sedang diset untuk auto-thread
# ══════════════════════════════════════════════════════════════
@bot.tree.command(name="ceksetting", description="Lihat channel yang sedang diset untuk auto-thread")
@app_commands.checks.has_permissions(manage_guild=True)  # hanya admin
async def ceksetting(interaction: discord.Interaction):
    db = load_db()
    channel_id = db.get("thread_channel")

    if not channel_id:
        await interaction.response.send_message(
            "⚠️ Belum ada channel yang diset! Pakai `/setchannel` dulu.",
            ephemeral=True
        )
        return

    await interaction.response.send_message(
        f"📌 Channel auto-thread saat ini: <#{channel_id}>",
        ephemeral=True
    )


# ══════════════════════════════════════════════════════════════
# SLASH COMMAND /resetchannel
# Untuk matikan/hapus setting channel auto-thread
# ══════════════════════════════════════════════════════════════
@bot.tree.command(name="resetchannel", description="Matikan fitur auto-thread (khusus admin)")
@app_commands.checks.has_permissions(manage_guild=True)  # hanya admin
async def resetchannel(interaction: discord.Interaction):
    db = load_db()
    db.pop("thread_channel", None)  # hapus setting channel dari JSON
    save_db(db)

    await interaction.response.send_message(
        "✅ Setting channel auto-thread berhasil dihapus!",
        ephemeral=True
    )


# ══════════════════════════════════════════════════════════════
# EVENT ON_MESSAGE
# Jalan otomatis setiap ada pesan masuk di server
# ══════════════════════════════════════════════════════════════
@bot.event
async def on_message(message):

    # ── Skip kalau pesan dari bot (hindari infinite loop) ──
    if message.author.bot:
        return

    # ── Ambil setting channel dari JSON ──
    db = load_db()
    thread_channel_id = db.get("thread_channel")

    # ── Kalau belum ada channel yang diset, skip ──
    if not thread_channel_id:
        return

    # ── Cek apakah pesan masuk di channel yang sudah diset ──
    if message.channel.id == thread_channel_id:

        # ── Kalau pesan TIDAK ada foto/video → hapus otomatis ──
        if not message.attachments:
            await message.delete()  # hapus pesan text

            # Kirim peringatan ke user
            warning = await message.channel.send(
                f"⚠️ {message.author.mention} "
                f"Channel ini hanya untuk foto/video ya!"
            )
            await asyncio.sleep(5)   # tunggu 5 detik
            await warning.delete()   # hapus pesan peringatan
            return

        # ── Kalau pesan ada foto/video → buat thread otomatis ──
        for attachment in message.attachments:
            # Cek apakah attachment nya gambar atau video
            is_image = attachment.content_type and "image" in attachment.content_type
            is_video = attachment.content_type and "video" in attachment.content_type

            if is_image or is_video:
                # Buat thread di bawah pesan foto/video
                thread = await message.create_thread(
                    name=f"📸 {message.author.display_name}",
                    auto_archive_duration=1440  # archive setelah 24 jam tidak aktif
                                                # bisa diganti: 60, 1440, 4320, 10080
                )
                # Kirim pesan sambutan di dalam thread
                await thread.send(
                    "💬 Comment di sini ya!"
                )

    # ── Wajib ada ini biar prefix command (!) tetap jalan ──
    await bot.process_commands(message)

# ══════════════════════════════════════════════════════════════
# JALANKAN BOT
# Token diambil dari environment variable (lebih aman)
# Jangan pernah tulis token langsung di kode!
# ══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)

    TOKEN = os.getenv("DISCORD_BOT_TOKEN")  # ambil token dari environment variable
    if not TOKEN:
        raise ValueError("❌ Environment variable DISCORD_BOT_TOKEN tidak ditemukan.")
        
# Jalankan web server di thread terpisah  ← TAMBAH INI
    thread = threading.Thread(target=run_server)
    thread.daemon = True
    thread.start()
    
    bot.run(TOKEN)
