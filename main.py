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
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'r') as f:
                content = f.read().strip()
                if content:
                    event_data = json.loads(content)
                else:
                    event_data = {}
        else:
            event_data = {}
    except (json.JSONDecodeError, IOError) as e:
        print(f"Error loading data: {e}")
        event_data = {}

def save_data():
    try:
        with open(DATA_FILE, 'w') as f:
            json.dump(event_data, f, indent=2)
    except IOError as e:
        print(f"Error saving data: {e}")

def get_config():
    if not os.path.exists(CONFIG_FILE):
        raise FileNotFoundError("Missing config.json")
    with open(CONFIG_FILE) as f:
        return json.load(f)

# --- Background Tasks ---
@tasks.loop(hours=24)
async def delete_old_threads():
    """Delete threads older than 7 days"""
    config = get_config()
    category_id = config.get("event_forum_category")
    
    if not category_id:
        return
        
    category = bot.get_channel(category_id)
    if not category or not isinstance(category, discord.ForumChannel):
        return
    
    cutoff_date = datetime.now() - timedelta(days=7)
    threads_to_remove = []
    
    for thread_id, data in event_data.items():
        created_at = datetime.fromisoformat(data.get("created_at", ""))
        if created_at < cutoff_date:
            thread = category.get_thread(int(thread_id))
            if thread:
                try:
                    await thread.delete()
                except:
                    pass  # Thread might already be deleted
            threads_to_remove.append(thread_id)
    
    # Remove from data
    for thread_id in threads_to_remove:
        del event_data[thread_id]
    
    if threads_to_remove:
        save_data()

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

        try:
            thread_with_message = await category.create_thread(
                name=f"event-{interaction.user.name}-{int(datetime.now().timestamp())}", 
                content=f"**Event Description:**\n{description}"
            )
            thread = thread_with_message.thread
            event_data[str(thread.id)] = {
                "creator": interaction.user.id,
                "created_at": datetime.now().isoformat(),
                "description": description
            }
            save_data()
            await interaction.response.send_message(f"Event thread created: {thread.mention}", ephemeral=True)
        except discord.HTTPException as e:
            await interaction.response.send_message(f"Error creating thread: {str(e)}", ephemeral=True)

    elif action.value == "close":
        if not thread_name:
            await interaction.response.send_message("Please provide the thread name to close.", ephemeral=True)
            return

        category = interaction.guild.get_channel(category_id)
        if not category or not isinstance(category, discord.ForumChannel):
            await interaction.response.send_message("Forum category is not set up correctly.", ephemeral=True)
            return

        # Find thread by name (check both active and archived threads)
        thread = None
        all_threads = list(category.threads)
        
        # Also check archived threads
        async for archived_thread in category.archived_threads(limit=100):
            all_threads.append(archived_thread)
        
        for t in all_threads:
            if t.name == thread_name:
                thread = t
                break

        if not thread:
            await interaction.response.send_message(f"Thread '{thread_name}' not found.", ephemeral=True)
            return

        # Check if user has permission to close this thread
        thread_data = event_data.get(str(thread.id))
        if thread_data and thread_data.get("creator") != interaction.user.id:
            await interaction.response.send_message("You can only close threads that you created.", ephemeral=True)
            return

        try:
            # Remove from event data and close thread
            if str(thread.id) in event_data:
                del event_data[str(thread.id)]
                save_data()

            await thread.edit(archived=True, locked=True)
            await interaction.response.send_message(f"Event thread '{thread_name}' has been closed.", ephemeral=True)
        except discord.HTTPException as e:
            await interaction.response.send_message(f"Error closing thread: {str(e)}", ephemeral=True)

# --- Run Bot ---
if __name__ == "__main__":
    token = os.getenv("DISCORD_BOT_TOKEN")
    if not token:
        config = get_config()
        token = config.get("bot_token")
    
    if not token:
        print("❌ Bot token not found. Set DISCORD_BOT_TOKEN in Secrets or add 'bot_token' to config.json.")
    else:
        bot.run(token)
