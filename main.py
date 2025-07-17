import discord
from discord import app_commands
from discord.ext import commands, tasks
import asyncio
import json
import os
from datetime import datetime, timedelta

CONFIG_FILE = 'config.json'
DATA_FILE = 'data.json'

intents = discord.Intents.default()
intents.guilds = True
intents.messages = True
intents.message_content = False
intents.guild_messages = True

bot = commands.Bot(command_prefix="!", intents=intents)

event_data = {}  # Loaded from file

# --- Load/Save Data ---
def load_data():
    global event_data
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            event_data = json.load(f)
    else:
        event_data = {}

def save_data():
    with open(DATA_FILE, 'w') as f:
        json.dump(event_data, f, indent=2)

def get_config():
    if not os.path.exists(CONFIG_FILE):
        raise FileNotFoundError("Missing config.json")
    with open(CONFIG_FILE) as f:
        return json.load(f)

# --- Slash Command Tree ---
@bot.event
async def on_ready():
    load_data()
    await bot.tree.sync()
    delete_old_threads.start()
    print(f'✅ Bot connected as {bot.user}')

@bot.tree.command(name="event", description="Create or manage an event")
@app_commands.describe(action="Create or close an event", description="Event description if creating", thread_name="Name of the thread to close")
@app_commands.rename(action='action', description='description', thread_name='thread_name')
@app_commands.choices(action=[
    app_commands.Choice(name="create", value="create"),
    app_commands.Choice(name="close", value="close")
])
async def event_handler(interaction: discord.Interaction, action: app_commands.Choice[str], description: str = None, thread_name: str = None):
    config = get_config()
    category_id = config.get("event_forum_category")

    if action.value == "create":
        if not description:
            await interaction.response.send_message("Please provide a description for the event.", ephemeral=True)
            return

        category = interaction.guild.get_channel(category_id)
        if not category or not isinstance(category, discord.ForumChannel):
            await interaction.response.send_message("Forum category is not set up correctly.", ephemeral=True)
            return

        thread = await category.create_thread(name=f"event-{interaction.user.name}-{int(datetime.now().timestamp())}", content=description)
        event_data[str(thread.id)] =_
