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

# ======== WELCOME EVENT =======
@bot.event
async def on_member_join(member):
    cfg = get_config()
    channel = bot.get_channel(cfg["WELCOME_CHANNEL_ID"])
    if channel:
        embed = discord.Embed(
            title="Bienvenue sur Pyradia Network !",
            description=f"{member.mention}, nous te souhaitons la bienvenue !",
            color=0x2ecc71
        )
        await channel.send(embed=embed)

# ======= GIVEAWAY SYSTEM =======
class GiveawayView(ui.View):
    def __init__(self, message_id, ends_at):
        super().__init__(timeout=None)
        self.message_id = str(message_id)
        self.ends_at = ends_at

    @ui.button(label="🎉 Participer", style=discord.ButtonStyle.green, custom_id="giveaway_participate")
    async def participate(self, interaction: Interaction, button: ui.Button):
        entries = load_json(ENTRY_FILE, {})
        entries.setdefault(self.message_id, [])
        if interaction.user.id in entries[self.message_id]:
            await interaction.response.send_message("Vous participez déjà à ce giveaway.", ephemeral=True)
            return
        entries[self.message_id].append(interaction.user.id)
        save_json(ENTRY_FILE, entries)
        await interaction.response.send_message(
            "Votre participation a été prise en compte. Bonne chance !",
            ephemeral=True
        )

async def update_giveaway_embed(message, prize, winners, ends_at):
    now = int(asyncio.get_event_loop().time())
    remaining = max(0, ends_at - now)
    time_str = str(timedelta(seconds=remaining))
    embed = discord.Embed(
        title="🎉 Giveaway Pyradia",
        description=f"**Prix :** {prize}\n**Nombre de gagnants :** {winners}\n**Temps restant :** {time_str}\n\nCliquez sur 🎉 pour participer !",
        color=0xf1c40f
    )
    await message.edit(embed=embed)

@bot.tree.command(name="giveaway", description="Créer un giveaway")
@app_commands.default_permissions(administrator=True)
@app_commands.describe(prize="Prix à gagner", winners="Nombre de gagnants", duration="Durée (minutes)")
async def giveaway(interaction: Interaction, prize: str, winners: int = 1, duration: int = 5):
    try:
        giveaways = load_json(GIVEAWAY_FILE, {})
        end_time = int(asyncio.get_event_loop().time() + duration * 60)
        now = int(asyncio.get_event_loop().time())
        time_str = str(timedelta(seconds=max(0, end_time - now)))
        embed = discord.Embed(
            title="🎉 Giveaway Pyradia",
            description=f"**Prix :** {prize}\n**Nombre de gagnants :** {winners}\n**Temps restant :** {time_str}\n\nCliquez sur 🎉 pour participer !",
            color=0xf1c40f
        )
        msg = await interaction.channel.send(embed=embed, view=GiveawayView(0, end_time))
        giveaways[str(msg.id)] = {
            "prize": prize,
            "winners": winners,
            "end_time": end_time,
            "channel_id": msg.channel.id
        }
        save_json(GIVEAWAY_FILE, giveaways)
        await msg.edit(view=GiveawayView(msg.id, end_time))
        await interaction.response.send_message("Giveaway lancé avec succès !", ephemeral=True)
    except Exception as e:
        await log_and_send_error(interaction, f"Erreur création giveaway: {e}")

@tasks.loop(seconds=10)
async def check_giveaways():
    now = int(asyncio.get_event_loop().time())
    giveaways = load_json(GIVEAWAY_FILE, {})
    entries = load_json(ENTRY_FILE, {})
    ended = []
    for msg_id, data in giveaways.items():
        try:
            channel = bot.get_channel(data["channel_id"])
            if not channel: continue
            message = await channel.fetch_message(int(msg_id))
            if now < data["end_time"]:
                await update_giveaway_embed(message, data["prize"], data["winners"], data["end_time"])
            else:
                participants = entries.get(msg_id, [])
                winners = []
                if participants:
                    random.shuffle(participants)
                    for uid in participants[:data["winners"]]:
                        try:
                            user = await bot.fetch_user(uid)
                            winners.append(user.mention)
                        except: continue
                    winners_text = ", ".join(winners)
                    msg = f"🎉 **Giveaway terminé !**\nPrix : **{data['prize']}**\nGagnant(s) : {winners_text}"
                else:
                    msg = f"Giveaway terminé. Aucun participant pour **{data['prize']}**."
                await channel.send(msg)
                ended.append(msg_id)
        except Exception as e:
            logging.warning(f"Erreur maj giveaway ou fin: {e}")
            continue
    for msg_id in ended:
        giveaways.pop(msg_id)
        if msg_id in entries: entries.pop(msg_id)
    if ended:
        save_json(GIVEAWAY_FILE, giveaways)
        save_json(ENTRY_FILE, entries)

# ======= TICKET PANEL & STATUS SYSTEM =======
TICKET_STATUSES = {
    "open":    {"label": "Ouvert", "emoji": "🟢", "color": 0x2ecc71},
    "pending": {"label": "En attente", "emoji": "🟡", "color": 0xf1c40f},
    "solved":  {"label": "Résolu", "emoji": "🔵", "color": 0x3498db},
    "closed":  {"label": "Fermé", "emoji": "🔴", "color": 0xe74c3c},
}

def get_status_embed(user, category, status="open"):
    status_obj = TICKET_STATUSES.get(status, TICKET_STATUSES["open"])
    embed = discord.Embed(
        title=f"{status_obj['emoji']} Ticket {category} • {status_obj['label']}",
        description=f"{user.mention}, merci d'expliquer précisément votre demande.\nUn membre du staff vous répondra rapidement.",
        color=status_obj["color"]
    )
    return embed

class TicketPanelView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="Créer un ticket", style=discord.ButtonStyle.blurple)
    async def open_ticket(self, interaction: Interaction, button: ui.Button):
        await interaction.response.send_message(
            "Choisissez la catégorie de votre ticket :",
            view=TicketCategoryView(), ephemeral=True
        )

class TicketCategory(ui.Select):
    def __init__(self):
        cfg = get_config()
        options = [
            discord.SelectOption(label=cat["label"], description=cat["desc"])
            for cat in cfg["ticket_categories"]
        ]
        super().__init__(
            placeholder="Catégorie du ticket",
            min_values=1, max_values=1, options=options
        )

    async def callback(self, interaction: Interaction):
        category = self.values[0]
        cfg = get_config()
        cat_config = next((cat for cat in cfg["ticket_categories"] if cat["label"] == category), None)
        guild = interaction.guild
        if not cat_config or not cat_config.get("category_id"):
            await log_and_send_error(interaction, f"Catégorie Discord non trouvée ou ID manquant pour {category}")
            return
        discord_category = guild.get_channel(cat_config["category_id"])
        if not isinstance(discord_category, discord.CategoryChannel):
            await log_and_send_error(interaction, f"L'ID {cat_config['category_id']} n'est pas une catégorie Discord valide")
            return

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True)
        }
        staff_role = guild.get_role(cfg["STAFF_ROLE_ID"])
        if staff_role:
            overwrites[staff_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_messages=True)
        try:
            ticket_channel = await guild.create_text_channel(
                name=f"ticket-{interaction.user.name}",
                overwrites=overwrites,
                category=discord_category,
                topic=f"Ticket {category} | {interaction.user.display_name}"
            )
            embed = get_status_embed(interaction.user, category, status="open")
            status_view = TicketStatusView(ticket_channel, interaction.user, category)
            await ticket_channel.send(embed=embed, view=status_view)
            await interaction.response.send_message(
                f"Votre ticket ({category}) est ouvert : {ticket_channel.mention}", ephemeral=True
            )
        except Exception as e:
            await log_and_send_error(interaction, f"Erreur création ticket: {e}")

class TicketCategoryView(ui.View):
    def __init__(self):
        super().__init__(timeout=120)
        self.add_item(TicketCategory())

class TicketStatusView(ui.View):
    def __init__(self, channel, user, category):
        super().__init__(timeout=None)
        self.channel = channel
        self.user = user
        self.category = category
        self.status = "open"

    @ui.button(label="En attente", style=discord.ButtonStyle.gray, emoji="🟡")
    async def set_pending(self, interaction: Interaction, button: ui.Button):
        await self.update_status(interaction, "pending")

    @ui.button(label="Résolu", style=discord.ButtonStyle.green, emoji="🔵")
    async def set_solved(self, interaction: Interaction, button: ui.Button):
        await self.update_status(interaction, "solved")

    @ui.button(label="Fermer", style=discord.ButtonStyle.red, emoji="🔴")
    async def close(self, interaction: Interaction, button: ui.Button):
        await self.update_status(interaction, "closed")
        await interaction.followup.send("Le ticket sera supprimé dans 5 secondes.", ephemeral=True)
        await asyncio.sleep(5)
        await self.channel.delete()

    async def update_status(self, interaction, status):
        self.status = status
        embed = get_status_embed(self.user, self.category, status)
        await interaction.response.edit_message(embed=embed, view=self if status != "closed" else None)

@bot.tree.command(name="ticketpanel", description="Afficher (ou re-créer) le panel de création de tickets (admin uniquement)")
@app_commands.default_permissions(administrator=True)
async def ticketpanel(interaction: Interaction):
    cfg = get_config()
    channel = bot.get_channel(cfg["TICKETS_PANEL_CHANNEL_ID"])
    if not channel:
        await interaction.response.send_message("Salon tickets introuvable.", ephemeral=True)
        return
    embed = discord.Embed(
        title="🎟️ Ouvrir un ticket d'assistance Pyradia",
        description="Besoin d'aide ou d'un support ? Cliquez ci-dessous pour ouvrir un ticket, puis choisissez la catégorie.",
        color=0x3498db
    )
    await channel.send(embed=embed, view=TicketPanelView())
    await interaction.response.send_message("Panel envoyé avec succès.", ephemeral=True)

# ======== PANEL DE CONFIGURATION (ADMIN) =======
@bot.tree.command(name="config_ticket", description="Panneau de configuration des tickets (admin)")
@app_commands.default_permissions(administrator=True)
@app_commands.describe(action="Action", key="Clé à modifier", value="Valeur ou JSON à appliquer")
async def config_ticket(interaction: Interaction, action: str, key: str = "", value: str = ""):
    cfg = get_config()
    if action == "voir":
        await interaction.response.send_message(
            f"Config actuelle :\n```json\n{json.dumps(cfg, indent=4, ensure_ascii=False)}```",
            ephemeral=True
        )
    elif action == "set":
        if key in cfg:
            if key.endswith("_ID"):
                try: cfg[key] = int(value)
                except: return await interaction.response.send_message("Valeur ID non valide.", ephemeral=True)
            else:
                cfg[key] = value
            set_config(cfg)
            await interaction.response.send_message("Valeur modifiée !", ephemeral=True)
        else:
            await interaction.response.send_message("Clé inconnue.", ephemeral=True)
    elif action == "addcat":
        try:
            cat = json.loads(value)
            if not all(k in cat for k in ("label", "desc", "category_id")):
                raise Exception("Il manque des champs.")
            cfg["ticket_categories"].append(cat)
            set_config(cfg)
            await interaction.response.send_message("Catégorie ajoutée !", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"Erreur ajout catégorie : {e}", ephemeral=True)
    elif action == "delcat":
        old = len(cfg["ticket_categories"])
        cfg["ticket_categories"] = [c for c in cfg["ticket_categories"] if c["label"] != key]
        set_config(cfg)
        if len(cfg["ticket_categories"]) < old:
            await interaction.response.send_message("Catégorie supprimée !", ephemeral=True)
        else:
            await interaction.response.send_message("Catégorie introuvable.", ephemeral=True)
    else:
        await interaction.response.send_message(
            "Action inconnue. Actions possibles : voir, set, addcat, delcat.", ephemeral=True)

# -------- STATUS PERSONNALISÉ --------
@bot.tree.command(name="setstatus", description="Change le status du bot")
@app_commands.describe(type="Type: playing, watching, listening, streaming", texte="Texte à afficher")
async def setstatus(interaction: Interaction, type: str, texte: str):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("Tu dois être admin.", ephemeral=True)
        return
    type = type.lower()
    if type == "playing":
        await bot.change_presence(activity=discord.Game(name=texte))
    elif type == "watching":
        await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name=texte))
    elif type == "listening":
        await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name=texte))
    elif type == "streaming":
        await bot.change_presence(activity=discord.Streaming(name=texte, url="https://twitch.tv/voidgiveaways"))
    else:
        await interaction.response.send_message("Type invalide (playing/watching/listening/streaming)", ephemeral=True)
        return
    await interaction.response.send_message(f"Status changé : {type} {texte}", ephemeral=True)

# ======= SHUTDOWN =======
@bot.tree.command(name="shutdown", description="Éteindre le bot Pyradia (admin uniquement)")
@app_commands.default_permissions(administrator=True)
async def shutdown(interaction: Interaction):
    await interaction.response.send_message("Arrêt du bot... (commande exécutée par un administrateur)", ephemeral=True)
    await bot.close()
    sys.exit(0)

@bot.event
async def on_ready():
    check_giveaways.start()
    try:
        # Synchronisation globale (ou pour le serveur spécifique)
        await bot.tree.sync(guild=discord.Object(id=GUILD_ID))
        logging.info(f"{bot.user} prêt et synchronisé sur le serveur {GUILD_ID} !")
    except Exception as e:
        logging.error(f"Erreur synchronisation slash: {e}")

if __name__ == "__main__":
    try:
        if not os.path.exists(CONFIG_FILE):
            save_json(CONFIG_FILE, DEFAULT_CONFIG)
        bot.run("MTM5MTg3Mzg4NTA3NDYyMDQ5Ng.Gg_RSq.9T2WOrd5Zeu6xGxkKa6Q3hShNYFRdAeV4Q2zfw")  # Remplace par ton token !
    except Exception as e:
        logging.critical(f"Erreur au lancement du bot : {e}")
