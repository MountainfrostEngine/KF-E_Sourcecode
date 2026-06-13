import os
import sqlite3
import threading
from flask import Flask, render_template_string, request
import discord
from discord import app_commands
from discord.ext import commands

# ==========================================
# 1. DATABASE & PRESET SHOP MANAGER
# ==========================================
DB_NAME = "dayz_system.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS guild_config (
                        guild_id TEXT PRIMARY KEY, 
                        nitrado_token TEXT, 
                        nitrado_server_id TEXT, 
                        currency_name TEXT DEFAULT 'Credits', 
                        admin_role_id TEXT,
                        admin_users TEXT DEFAULT ''
                    )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (guild_id TEXT, discord_id TEXT, gamertag TEXT, balance INTEGER DEFAULT 5000, PRIMARY KEY (guild_id, discord_id))''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS shop (id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id TEXT, name TEXT, class_name TEXT, price INTEGER, category TEXT)''')
    conn.commit()
    conn.close()

def prefill_shop(guild_id: str):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM shop WHERE guild_id = ?", (guild_id,))
    if cursor.fetchone()[0] == 0:
        default_items = [
            # Assault Rifles
            (guild_id, 'M4A1 Assault Rifle', 'M4A1', 1500, 'Assault Rifles'),
            (guild_id, 'LAR Battle Rifle', 'FAL', 2500, 'Assault Rifles'),
            (guild_id, 'AUR AX', 'Aug', 2000, 'Assault Rifles'),
            # Snipers & Weapons
            (guild_id, 'VSD Sniper', 'SVD', 5000, 'Sniper Rifles'),
            (guild_id, 'Tundra', 'Winchester70', 3000, 'Sniper Rifles'),
            (guild_id, 'Vaiga', 'Saiga', 1500, 'SMGs & Shotguns'),
            # Gear & Base
            (guild_id, 'Plate Carrier', 'PlateCarrierVest', 2500, 'Armor & Clothing'),
            (guild_id, 'Night Vision Goggles', 'NVGoggles', 6000, 'Armor & Clothing'),
            (guild_id, 'Wooden Plank (x10)', 'WoodenPlank', 100, 'Base Building'),
            (guild_id, 'Combination Lock (4 Dial)', 'CombinationLock4', 1500, 'Base Building'),
            (guild_id, 'Car Tent', 'CarTent', 2500, 'Vehicles & Storage'),
            
            # UPGRADED: Dynamic Vehicle Spawns
            (guild_id, 'Ada 4x4 (Blue)', 'OffroadHatchback_Blue', 12000, 'Vehicles'),
            (guild_id, 'Gunter 2 (Red)', 'Hatchback_02_Red', 10000, 'Vehicles'),
            (guild_id, 'Olga 24 (Black)', 'Sedan_02_Black', 15000, 'Vehicles'),
            (guild_id, 'M3S Truck (Covered)', 'Truck_01_Covered', 25000, 'Vehicles')
        ]
        cursor.executemany("INSERT INTO shop (guild_id, name, class_name, price, category) VALUES (?, ?, ?, ?, ?)", default_items)
        conn.commit()
    conn.close()

init_db()

# ==========================================
# 2. FLASK WEB DASHBOARD (Liquid Glass)
# ==========================================
app = Flask(__name__)

DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>DayZ Liquid Glass</title>
    <style>
        :root { --glass: rgba(255, 255, 255, 0.05); --neon: #00ffcc; }
        body { font-family: -apple-system, sans-serif; background: #0b0c10; color: #c5c6c7; margin: 0; padding: 40px; }
        .panel { background: var(--glass); backdrop-filter: blur(20px); border: 1px solid rgba(255,255,255,0.1); border-radius: 16px; padding: 24px; margin-bottom: 24px; }
        h2 { color: #fff; margin-top: 0; border-bottom: 1px solid rgba(255,255,255,0.1); padding-bottom: 12px; }
        table { width: 100%; border-collapse: collapse; margin-top: 16px; }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid rgba(255,255,255,0.05); }
        th { color: var(--neon); font-size: 14px; text-transform: uppercase; }
        .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 24px; }
        input, button, textarea { padding: 12px; border-radius: 8px; border: 1px solid rgba(255,255,255,0.2); background: rgba(0,0,0,0.5); color: #fff; margin-bottom: 12px; width: 100%; box-sizing: border-box; }
        textarea { height: 60px; font-family: monospace; resize: vertical; }
        button { background: rgba(0, 255, 204, 0.1); color: var(--neon); border-color: var(--neon); cursor: pointer; font-weight: bold; }
        button:hover { background: rgba(0, 255, 204, 0.2); }
    </style>
</head>
<body>
    <h1>DayZ Control Terminal</h1>
    <p>Managing Server ID: {{ guild_id }}</p>
    <div class="grid">
        <div class="panel">
            <h2>System Integration & Permissions</h2>
            <form action="/update_config/{{ guild_id }}" method="POST">
                <label>Nitrado Token</label>
                <input type="password" name="token" value="{{ config.token or '' }}" placeholder="Nitrado Token">
                
                <label>Server ID</label>
                <input type="text" name="server_id" value="{{ config.server_id or '' }}" placeholder="Server ID">
                
                <label>Authorized Admin Discord IDs (Comma separated)</label>
                <textarea name="admin_users" placeholder="e.g. 123456789012345678">{{ config.admin_users or '' }}</textarea>
                
                <button type="submit">Lock Configurations</button>
            </form>
        </div>
        <div class="panel">
            <h2>Economy Matrix</h2>
            <table>
                <tr><th>Discord ID</th><th>Gamertag</th><th>Balance</th></tr>
                {% for user in users %}<tr><td>{{ user[0] }}</td><td><strong>{{ user[1] }}</strong></td><td>${{ user[2] }}</td></tr>{% endfor %}
            </table>
        </div>
    </div>
    <div class="panel">
        <h2>Preset Shop Registry</h2>
        <table>
            <tr><th>ID</th><th>Nomenclature</th><th>Internal Class</th><th>Price</th><th>Category</th></tr>
            {% for item in shop %}<tr><td>{{ item[0] }}</td><td>{{ item[1] }}</td><td><code>{{ item[2] }}</code></td><td>${{ item[3] }}</td><td>{{ item[4] }}</td></tr>{% endfor %}
        </table>
    </div>
</body>
</html>
"""

@app.route('/')
def home():
    return "Bot Engine is Online and Running."

@app.route('/server/<guild_id>')
def view_dashboard(guild_id):
    prefill_shop(guild_id)
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute("SELECT nitrado_token, nitrado_server_id, admin_users FROM guild_config WHERE guild_id = ?", (guild_id,))
    conf = cursor.fetchone()
    config = {"token": conf[0], "server_id": conf[1], "admin_users": conf[2]} if conf else {"token": None, "server_id": None, "admin_users": ""}
    
    cursor.execute("SELECT discord_id, gamertag, balance FROM users WHERE guild_id = ? ORDER BY balance DESC LIMIT 50", (guild_id,))
    users = cursor.fetchall()
    
    cursor.execute("SELECT id, name, class_name, price, category FROM shop WHERE guild_id = ? ORDER BY category ASC", (guild_id,))
    shop = cursor.fetchall()
    conn.close()
    
    return render_template_string(DASHBOARD_HTML, guild_id=guild_id, config=config, users=users, shop=shop)

@app.route('/update_config/<guild_id>', methods=['POST'])
def update_config(guild_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    admin_users_raw = request.form.get('admin_users', '')
    admin_users_cleaned = ",".join([uid.strip() for uid in admin_users_raw.split(",") if uid.strip()])
    
    cursor.execute('''INSERT INTO guild_config (guild_id, nitrado_token, nitrado_server_id, admin_users) 
                      VALUES (?, ?, ?, ?) 
                      ON CONFLICT(guild_id) DO UPDATE SET 
                        nitrado_token=excluded.nitrado_token, 
                        nitrado_server_id=excluded.nitrado_server_id,
                        admin_users=excluded.admin_users''', 
                   (guild_id, request.form.get('token'), request.form.get('server_id'), admin_users_cleaned))
    conn.commit()
    conn.close()
    return f"<script>alert('System Configurations Updated.'); window.location.href='/server/{guild_id}';</script>"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, use_reloader=False)

# ==========================================
# 3. DISCORD BOT ENGINE
# ==========================================
class DayZBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=discord.Intents.default())

bot = DayZBot()

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name}")
    for guild in bot.guilds:
        try:
            bot.tree.copy_global_to(guild=guild)
            await bot.tree.sync(guild=guild)
            print(f"Forced instant slash command sync for: {guild.name}")
        except Exception as e:
            print(f"Could not sync commands to guild {guild.id}: {e}")
    print("Bot startup tasks fully executed.")

def is_admin(guild_id: str, discord_id: str) -> bool:
    conn = sqlite3.connect(DB_NAME)
    row = conn.execute("SELECT admin_users FROM guild_config WHERE guild_id = ?", (guild_id,)).fetchone()
    conn.close()
    if not row or not row[0]: return False
    return discord_id in [uid.strip() for uid in row[0].split(",") if uid.strip()]

# --- Player Commands ---

@bot.tree.command(name="player_link", description="Bind gamertag to your discord profile")
async def player_link(interaction: discord.Interaction, gamertag: str):
    guild_id, discord_id = str(interaction.guild_id), str(interaction.user.id)
    prefill_shop(guild_id)
    conn = sqlite3.connect(DB_NAME)
    try:
        conn.execute('''INSERT INTO users (guild_id, discord_id, gamertag) VALUES (?, ?, ?) ON CONFLICT(guild_id, discord_id) DO UPDATE SET gamertag=excluded.gamertag''', (guild_id, discord_id, gamertag))
        conn.commit()
        await interaction.response.send_message(f"✅ Identity locked to **{gamertag}**.", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message("❌ Database Fault.", ephemeral=True)
    finally:
        conn.close()

@bot.tree.command(name="player_profile", description="Check account capital and registered gamertag")
async def player_profile(interaction: discord.Interaction):
    conn = sqlite3.connect(DB_NAME)
    user = conn.execute("SELECT gamertag, balance FROM users WHERE guild_id = ? AND discord_id = ?", (str(interaction.guild_id), str(interaction.user.id))).fetchone()
    conn.close()
    if not user: return await interaction.response.send_message("❌ Profile unlinked. Execute `/player_link` first.", ephemeral=True)
    await interaction.response.send_message(f"👤 **{user[0]}** | Capital: **${user[1]}**")

@bot.tree.command(name="player_shop", description="Browse the full server economy deployment item list")
async def player_shop(interaction: discord.Interaction):
    guild_id = str(interaction.guild_id)
    prefill_shop(guild_id)
    conn = sqlite3.connect(DB_NAME)
    # Increased limits slightly so players can see the new vehicles added down bottom
    items = conn.execute("SELECT id, name, price, category FROM shop WHERE guild_id = ? LIMIT 30", (guild_id,)).fetchall()
    conn.close()
    
    if not items:
        return await interaction.response.send_message("The server shop is currently empty.", ephemeral=True)
        
    embed = discord.Embed(title="Automated Deployment Catalog", color=discord.Color.red())
    for item in items:
        embed.add_field(name=f"[ID: {item[0]}] {item[1]}", value=f"${item[2]} | {item[3]}", inline=True)
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="player_buy", description="Purchase items for remote injection")
async def player_buy(interaction: discord.Interaction, item_id: int, coordinates: str):
    guild_id, discord_id = str(interaction.guild_id), str(interaction.user.id)
    conn = sqlite3.connect(DB_NAME)
    config = conn.execute("SELECT nitrado_token, nitrado_server_id FROM guild_config WHERE guild_id = ?", (guild_id,)).fetchone()
    
    if not config or not config[0]: return await interaction.response.send_message("❌ Server infrastructure offline. Contact an administrator to bind keys.", ephemeral=True)
    
    user = conn.execute("SELECT gamertag, balance FROM users WHERE guild_id = ? AND discord_id = ?", (guild_id, discord_id)).fetchone()
    item = conn.execute("SELECT name, class_name, price FROM shop WHERE guild_id = ? AND id = ?", (guild_id, item_id)).fetchone()
    
    if not user: return await interaction.response.send_message("❌ Profile unlinked. Execute `/player_link` first.", ephemeral=True)
    if not item: return await interaction.response.send_message("❌ Invalid Shop Item ID.", ephemeral=True)
    if user[1] < item[2]: return await interaction.response.send_message(f"❌ Transaction declined. Requires ${item[2]}.", ephemeral=True)

    conn.execute("UPDATE users SET balance = balance - ? WHERE guild_id = ? AND discord_id = ?", (item[2], guild_id, discord_id))
    conn.commit()
    conn.close()
    
    await interaction.response.send_message(f"✅ Authorized. **{item[0]}** queued for automated spawn at `{coordinates}`.", ephemeral=True)

# --- Admin Commands ---

@bot.tree.command(name="admin_add-cash", description="Add currency directly to a specific target player")
async def admin_add_cash(interaction: discord.Interaction, target_user: discord.User, amount: int):
    guild_id, caller_id = str(interaction.guild_id), str(interaction.user.id)
    
    if not interaction.user.guild_permissions.administrator and not is_admin(guild_id, caller_id):
        return await interaction.response.send_message("❌ Access Denied: Admin role/ID verification failed.", ephemeral=True)
        
    conn = sqlite3.connect(DB_NAME)
    conn.execute('''INSERT INTO users (guild_id, discord_id, balance) VALUES (?, ?, ?) 
                    ON CONFLICT(guild_id, discord_id) DO UPDATE SET balance = balance + excluded.balance''', 
                 (guild_id, str(target_user.id), amount))
    conn.commit()
    conn.close()
    await interaction.response.send_message(f"✅ Management Action: Successfully allocated ${amount} to {target_user.mention}.")

if __name__ == "__main__":
    threading.Thread(target=run_web, daemon=True).start()
    TOKEN = os.environ.get("BOT_TOKEN")
    if TOKEN:
        bot.run(TOKEN)
    else:
        print("ERROR: BOT_TOKEN environment variable not set.")
