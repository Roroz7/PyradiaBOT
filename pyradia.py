import discord
from discord import app_commands, Interaction, ui
from discord.ext import commands, tasks
import asyncio
import logging
import random
import json
import os
import sys
from datetime import timedelta
import threading
from flask import Flask

# ======== FLASK SERVER POUR RENDER =======
app = Flask("")

@app.route("/")
def home():
    return "Bot Discord Pyradia actif !"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# Lance le serveur Flask dans un thread séparé
threading.Thread(target=run_flask).start()

# ======== CONFIG =======
CONFIG_FILE = "config.json"
GIVEAWAY_FILE = "giveaways.json"
ENTRY_FILE = "giveaway_entries.json"
GUILD_ID = "1340357493729136640"

DEFAULT_CONFIG = {
    "WELCOME_CHANNEL_ID": 1340358054687805470,
    "TICKETS_PANEL_CHANNEL_ID": 1340463470558314537,
    "STAFF_ROLE_ID": 1340459345674244178,
    "ticket_categories": [
        {"label": "Boutique", "desc": "Support boutique Pyradia", "category_id": 1391895642753990656},
        {"label": "In-game", "desc": "Problème en jeu", "category_id": 1391895603172081734},
        {"label": "Autre", "desc": "Autre demande", "category_id": 1391895674580107364},
        {"label": "Recrutement staff", "desc": "formulaire de recrutement staff", "category_id": 1392282759870812262}
    ]
}

# ======== UTILS JSON =======
def load_json(filename, default):
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            try: return json.load(f)
            except: return default
    return default

def save_json(filename, data):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def get_config():
    cfg = load_json(CONFIG_FILE, DEFAULT_CONFIG)
    # vérifie les champs essentiels, sinon reset par défaut
    for key in DEFAULT_CONFIG:
        if key not in cfg: cfg[key] = DEFAULT_CONFIG[key]
    save_json(CONFIG_FILE, cfg)
    return cfg

def set_config(new_cfg):
    save_json(CONFIG_FILE, new_cfg)

async def log_and_send_error(interaction, error_msg):
    logging.error(error_msg)
    if interaction and not interaction.response.is_done():
        await interaction.response.send_message("❌ Une erreur est survenue. Contactez un administrateur.", ephemeral=True)

# ======== DISCORD INIT =======
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# ======== LE RESTE DE TON CODE =======
# (Bienvenue, Giveaway, Tickets, Config, SetStatus, Shutdown)
# Copie tout le code de ton bot ici à partir de ton fichier principal
# rien ne change dans le bot lui-même, juste Flask est lancé en parallèle

@bot.event
async def on_ready():
    check_giveaways.start()
    try:
        await bot.tree.sync()
        logging.info(f"{bot.user} prêt et synchronisé !")
    except Exception as e:
        logging.error(f"Erreur synchronisation slash: {e}")

if __name__ == "__main__":
    try:
        if not os.path.exists(CONFIG_FILE):
            save_json(CONFIG_FILE, DEFAULT_CONFIG)
        bot.run("MTM5MTg3Mzg4NTA3NDYyMDQ5Ng.Gg_RSq.9T2WOrd5Zeu6xGxkKa6Q3hShNYFRdAeV4Q2zfw")  # Remplace par ton token !
    except Exception as e:
        logging.critical(f"Erreur au lancement du bot : {e}")
