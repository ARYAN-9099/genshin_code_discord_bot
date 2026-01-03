import discord
from discord.ext import tasks
import discord.app_commands
import requests
import psycopg2
import os

TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))
DATABASE_URL = os.getenv("DATABASE_URL")

API_URL = "https://hoyo-codes.seria.moe/codes?game=genshin"

intents = discord.Intents.default()
client = discord.Client(intents=intents)
tree = discord.app_commands.CommandTree(client)

# ---------- database ----------

def get_db():
    return psycopg2.connect(DATABASE_URL, sslmode="require")

def init_db():
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS sent_codes (
                    code TEXT PRIMARY KEY
                )
            """)

def is_new_code(code):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM sent_codes WHERE code = %s", (code,))
            return cur.fetchone() is None

def mark_code_sent(code):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO sent_codes (code) VALUES (%s) ON CONFLICT DO NOTHING",
                (code,)
            )

# ---------- background task ----------

@tasks.loop(minutes=20)
async def check_codes():
    try:
        r = requests.get(API_URL, timeout=10)
        data = r.json()
    except Exception:
        return

    channel = client.get_channel(CHANNEL_ID)
    if channel is None:
        return

    for entry in data["codes"]:
        code = entry["code"]
        rewards = entry["rewards"] or "Rewards unknown"

        if is_new_code(code):
            redeem_url = f"https://genshin.hoyoverse.com/en/gift?code={code}"
            await channel.send(
                f"🎁 **New Genshin Impact Code!**\n"
                f"**Code:** `{code}`\n"
                f"**Rewards:** {rewards}\n"
                f"🔗 {redeem_url}"
            )
            mark_code_sent(code)

# ---------- slash command ----------

@tree.command(
    name="genshin_codes",
    description="Show all available Genshin Impact codes"
)
async def genshin_codes(interaction: discord.Interaction):
    await interaction.response.defer()

    try:
        r = requests.get(API_URL, timeout=10)
        data = r.json()
    except Exception:
        await interaction.followup.send("❌ Failed to fetch codes.")
        return

    lines = [
        f"`{c['code']}` — {c['rewards'] or 'Rewards unknown'}"
        for c in data["codes"]
    ]

    message = "\n".join(lines)
    if len(message) > 1900:
        message = message[:1900] + "\n..."

    await interaction.followup.send(
        f"🎁 **Available Genshin Impact Codes**\n{message}"
    )

# ---------- startup ----------

@client.event
async def on_ready():
    print(f"Logged in as {client.user}")
    init_db()
    await tree.sync()
    check_codes.start()

client.run(TOKEN)
