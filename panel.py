import discord
import asyncio
import io
from utils import *

# ═══════════════════════════════════════════
#  MODALS PANEL
# ═══════════════════════════════════════════

class ModalAjouterMot(discord.ui.Modal, title="➕ Ajouter un mot filtré"):
    mot = discord.ui.TextInput(label="Mot à filtrer", placeholder="Ex : insulte...", max_length=50)
    async def on_submit(self, i: discord.Interaction):
        add_custom(i.guild.id, self.mot.value)
        e = E("✅ Mot ajouté !", f"`{self.mot.value}` est maintenant filtré sur ce serveur.", 0x43B581)
        await i.response.send_message(embed=e, ephemeral=True)

class ModalRetirerMot(discord.ui.Modal, title="➖ Retirer un mot filtré"):
    mot = discord.ui.TextInput(label="Mot à retirer", placeholder="Ex : insulte...", max_length=50)
    async def on_submit(self, i: discord.Interaction):
        ok = del_custom(i.guild.id, self.mot.value)
        e = E("✅ Retiré !" if ok else "❌ Introuvable",
              f"`{self.mot.value}` {'retiré.' if ok else 'non trouvé dans la liste personnalisée.'}" ,
              0x43B581 if ok else 0xED4245)
        await i.response.send_message(embed=e, ephemeral=True)

class ModalImmuniserRole(discord.ui.Modal, title="🛡️ Immuniser un rôle"):
    role_id = discord.ui.TextInput(label="ID du rôle à immuniser", placeholder="Ex : 123456789012345678", max_length=20)
    async def on_submit(self, i: discord.Interaction):
        add_role_immunise(i.guild.id, self.role_id.value)
        role = i.guild.get_role(int(self.role_id.value))
        nom = role.name if role else self.role_id.value
        e = E("✅ Rôle immunisé !", f"Le rôle **{nom}** ne sera plus sanctionné pour les insultes.", 0x43B581)
        await i.response.send_message(embed=e, ephemeral=True)

class ModalRetirerImmunite(discord.ui.Modal, title="❌ Retirer l'immunité d'un rôle"):
    role_id = discord.ui.TextInput(label="ID du rôle", placeholder="Ex : 123456789012345678", max_length=20)
    async def on_submit(self, i: discord.Interaction):
        ok = del_role_immunise(i.guild.id, self.role_id.value)
        e = E("✅ Immunité retirée !" if ok else "❌ Introuvable",
              couleur=0x43B581 if ok else 0xED4245)
        await i.response.send_message(embed=e, ephemeral=True)

class ModalLockSalon(discord.ui.Modal, title="🔒 Lockdown d'un salon"):
    salon_id = discord.ui.TextInput(label="ID du salon", placeholder="Ex : 123456789012345678", max_length=20)
    def __init__(self, action): super().__init__(); self.action = action
    async def on_submit(self, i: discord.Interaction):
        await i.response.defer(ephemeral=True)
        try:
            ch = i.guild.get_channel(int(self.salon_id.value))
            if not ch: return await i.followup.send("❌ Salon introuvable.", ephemeral=True)
            if self.action == "lock":
                await ch.set_permissions(i.guild.default_role, send_messages=False)
                e = E("🔒 Salon verrouillé", f"{ch.mention} est verrouillé.", 0xED4245)
            else:
                await ch.set_permissions(i.guild.default_role, send_messages=None)
                e = E("🔓 Salon déverrouillé", f"{ch.mention} est accessible.", 0x43B581)
            await i.followup.send(embed=e, ephemeral=True)
        except Exception as ex:
            await i.followup.send(f"❌ Erreur : {ex}", ephemeral=True)

class ModalDefinirSalon(discord.ui.Modal, title="📌 Définir un salon"):
    salon_id = discord.ui.TextInput(label="ID du salon", placeholder="Ex : 123456789012345678", max_length=20)
    def __init__(self, key, label_key): super().__init__(); self.key = key; self.label_key = label_key
    async def on_submit(self, i: discord.Interaction):
        await i.response.defer(ephemeral=True)
        try:
            ch = i.guild.get_channel(int(self.salon_id.value))
            if not ch: return await i.followup.send("❌ Salon introuvable.", ephemeral=True)
            set_salon(i.guild.id, self.key, int(self.salon_id.value))
            e = E("✅ Salon défini !", f"Le salon **{self.label_key}** est maintenant {ch.mention}.", 0x43B581)
            await i.followup.send(embed=e, ephemeral=True)
        except Exception as ex:
            await i.followup.send(f"❌ Erreur : {ex}", ephemeral=True)

class ModalCreerSalon(discord.ui.Modal, title="➕ Créer un salon"):
    nom = discord.ui.TextInput(label="Nom du salon", placeholder="Ex : logs-modbot", max_length=50)
    def __init__(self, key, label_key): super().__init__(); self.key = key; self.label_key = label_key
    async def on_submit(self, i: discord.Interaction):
        await i.response.defer(ephemeral=True)
        try:
            ch = await i.guild.create_text_channel(self.nom.value)
            set_salon(i.guild.id, self.key, ch.id)
            e = E("✅ Salon créé !", f"Le salon {ch.mention} a été créé et défini comme **{self.label_key}**.", 0x43B581)
            await i.followup.send(embed=e, ephemeral=True)
        except Exception as ex:
            await i.followup.send(f"❌ Erreur : {ex}", ephemeral=True)

# ═══════════════════════════════════════════
#  SOUS-PANELS
# ═══════════════════════════════════════════

class VuePanelInsultes(discord.ui.View):
    def __init__(self): super().__init__(timeout=180)

    @discord.ui.button(label="➕ Ajouter mot", style=discord.ButtonStyle.danger, row=0)
    async def aj(self, i: discord.Interaction, b): await i.response.send_modal(ModalAjouterMot())

    @discord.ui.button(label="➖ Retirer mot", style=discord.ButtonStyle.secondary, row=0)
    async def rm(self, i: discord.Interaction, b): await i.response.send_modal(ModalRetirerMot())

    @discord.ui.button(label="📋 Voir la liste", style=discord.ButtonStyle.primary, row=0)
    async def lst(self, i: discord.Interaction, b):
        custom = get_custom(i.guild.id)
        e = E("🚫 Mots filtrés sur ce serveur", couleur=0xED4245)
        base_str = " • ".join([f"`{x}`" for x in INSULTES_BASE])
        if len(base_str) > 1024: base_str = base_str[:1020] + "..."
        e.add_field(name=f"📋 Par défaut ({len(INSULTES_BASE)})", value=base_str, inline=False)
        custom_str = (" • ".join([f"`{x}`" for x in custom])) if custom else "*Aucun mot personnalisé*"
        e.add_field(name=f"➕ Personnalisés ({len(custom)})", value=custom_str, inline=False)
        await i.response.send_message(embed=e, ephemeral=True)

    @discord.ui.button(label="🛡️ Immuniser un rôle", style=discord.ButtonStyle.success, row=1)
    async def imm(self, i: discord.Interaction, b): await i.response.send_modal(ModalImmuniserRole())

    @discord.ui.button(label="❌ Retirer immunité", style=discord.ButtonStyle.secondary, row=1)
    async def rimm(self, i: discord.Interaction, b): await i.response.send_modal(ModalRetirerImmunite())

    @discord.ui.button(label="📋 Rôles immunisés", style=discord.ButtonStyle.primary, row=1)
    async def lst_imm(self, i: discord.Interaction, b):
        roles = get_roles_immunises(i.guild.id)
        e = E("🛡️ Rôles immunisés", couleur=0x43B581)
        if roles:
            lignes = []
            for rid in roles:
                role = i.guild.get_role(int(rid))
                lignes.append(f"• {role.mention if role else rid}")
            e.description = "\n".join(lignes)
        else:
            e.description = "*Aucun rôle immunisé.*"
        await i.response.send_message(embed=e, ephemeral=True)

class VuePanelSecurite(discord.ui.View):
    def __init__(self): super().__init__(timeout=180)

    @discord.ui.button(label="🔒 Lockdown serveur", style=discord.ButtonStyle.danger, row=0)
    async def lock_srv(self, i: discord.Interaction, b):
        await i.response.defer(ephemeral=True)
        count = 0
        for ch in i.guild.text_channels:
            try: await ch.set_permissions(i.guild.default_role, send_messages=False); count += 1
            except: pass
        update_cfg(i.guild.id, "lockdown", True)
        e = E("🔒 LOCKDOWN ACTIVÉ", f"**{count} salons** verrouillés.", 0xED4245)
        e.add_field(name="👮 Par", value=str(i.user), inline=True)
        await i.followup.send(embed=e, ephemeral=True)

    @discord.ui.button(label="🔓 Unlock serveur", style=discord.ButtonStyle.success, row=0)
    async def unlock_srv(self, i: discord.Interaction, b):
        await i.response.defer(ephemeral=True)
        count = 0
        for ch in i.guild.text_channels:
            try: await ch.set_permissions(i.guild.default_role, send_messages=None); count += 1
            except: pass
        update_cfg(i.guild.id, "lockdown", False)
        e = E("🔓 LOCKDOWN DÉSACTIVÉ", f"**{count} salons** déverrouillés.", 0x43B581)
        await i.followup.send(embed=e, ephemeral=True)

    @discord.ui.button(label="🔒 Lock un salon", style=discord.ButtonStyle.danger, row=0)
    async def lock_ch(self, i: discord.Interaction, b): await i.response.send_modal(ModalLockSalon("lock"))

    @discord.ui.button(label="🔓 Unlock un salon", style=discord.ButtonStyle.success, row=0)
    async def unlock_ch(self, i: discord.Interaction, b): await i.response.send_modal(ModalLockSalon("unlock"))

    @discord.ui.button(label="🛡️ Anti-Raid ON", style=discord.ButtonStyle.success, row=1)
    async def raid_on(self, i: discord.Interaction, b):
        update_cfg(i.guild.id, "antiraid", True)
        e = E("🛡️ Anti-Raid ACTIVÉ",
              "• Comptes < 7 jours → expulsion auto\n• Jointures massives (+5 en 10s) → alerte logs\n• Anti-spam de messages activé",
              0x43B581)
        await i.response.send_message(embed=e, ephemeral=True)

    @discord.ui.button(label="🛡️ Anti-Raid OFF", style=discord.ButtonStyle.secondary, row=1)
    async def raid_off(self, i: discord.Interaction, b):
        update_cfg(i.guild.id, "antiraid", False)
        e = E("🛡️ Anti-Raid DÉSACTIVÉ", "Protection anti-raid désactivée.", 0xED4245)
        await i.response.send_message(embed=e, ephemeral=True)

    @discord.ui.button(label="🚫 Anti-Invite ON", style=discord.ButtonStyle.danger, row=1)
    async def inv_on(self, i: discord.Interaction, b):
        update_cfg(i.guild.id, "anti_invite", True)
        e = E("🚫 Anti-Invite ACTIVÉ", "Les liens d'invitation Discord seront automatiquement supprimés.", 0x43B581)
        await i.response.send_message(embed=e, ephemeral=True)

    @discord.ui.button(label="🚫 Anti-Invite OFF", style=discord.ButtonStyle.secondary, row=1)
    async def inv_off(self, i: discord.Interaction, b):
        update_cfg(i.guild.id, "anti_invite", False)
        e = E("🚫 Anti-Invite DÉSACTIVÉ", "La détection des invitations est désactivée.", 0xED4245)
        await i.response.send_message(embed=e, ephemeral=True)

class VuePanelSalons(discord.ui.View):
    def __init__(self): super().__init__(timeout=180)

    SALONS = [
        ("salon_logs", "Logs"),
        ("salon_suggestions", "Suggestions"),
        ("salon_reports", "Reports"),
        ("salon_patchnotes", "Patch Notes"),
        ("salon_tickets", "Tickets"),
    ]

    async def _afficher_status(self, i: discord.Interaction):
        cfg = get_cfg(i.guild.id)
        e = E("📌 Salons configurés", couleur=0x5865F2)
        for key, label in self.SALONS:
            val = cfg.get(key)
            ch = i.guild.get_channel(val) if val else None
            e.add_field(name=f"#{label}", value=ch.mention if ch else "*Non défini*", inline=True)
        await i.response.send_message(embed=e, ephemeral=True)

    @discord.ui.button(label="📊 Voir les salons", style=discord.ButtonStyle.primary, row=0)
    async def voir(self, i: discord.Interaction, b): await self._afficher_status(i)

    @discord.ui.button(label="📝 Définir Logs", style=discord.ButtonStyle.secondary, row=0)
    async def def_logs(self, i, b): await i.response.send_modal(ModalDefinirSalon("salon_logs", "Logs"))

    @discord.ui.button(label="➕ Créer Logs", style=discord.ButtonStyle.success, row=0)
    async def cr_logs(self, i, b): await i.response.send_modal(ModalCreerSalon("salon_logs", "Logs"))

    @discord.ui.button(label="📝 Définir Suggestions", style=discord.ButtonStyle.secondary, row=1)
    async def def_sug(self, i, b): await i.response.send_modal(ModalDefinirSalon("salon_suggestions", "Suggestions"))

    @discord.ui.button(label="➕ Créer Suggestions", style=discord.ButtonStyle.success, row=1)
    async def cr_sug(self, i, b): await i.response.send_modal(ModalCreerSalon("salon_suggestions", "Suggestions"))

    @discord.ui.button(label="📝 Définir Reports", style=discord.ButtonStyle.secondary, row=2)
    async def def_rep(self, i, b): await i.response.send_modal(ModalDefinirSalon("salon_reports", "Reports"))

    @discord.ui.button(label="➕ Créer Reports", style=discord.ButtonStyle.success, row=2)
    async def cr_rep(self, i, b): await i.response.send_modal(ModalCreerSalon("salon_reports", "Reports"))

    @discord.ui.button(label="📝 Définir Patch Notes", style=discord.ButtonStyle.secondary, row=3)
    async def def_pn(self, i, b): await i.response.send_modal(ModalDefinirSalon("salon_patchnotes", "Patch Notes"))

    @discord.ui.button(label="➕ Créer Patch Notes", style=discord.ButtonStyle.success, row=3)
    async def cr_pn(self, i, b): await i.response.send_modal(ModalCreerSalon("salon_patchnotes", "Patch Notes"))

    @discord.ui.button(label="📝 Définir Tickets", style=discord.ButtonStyle.secondary, row=4)
    async def def_tkt(self, i, b): await i.response.send_modal(ModalDefinirSalon("salon_tickets", "Tickets"))

    @discord.ui.button(label="➕ Créer Tickets", style=discord.ButtonStyle.success, row=4)
    async def cr_tkt(self, i, b): await i.response.send_modal(ModalCreerSalon("salon_tickets", "Tickets"))

class VuePanelStats(discord.ui.View):
    def __init__(self): super().__init__(timeout=180)

    @discord.ui.button(label="📊 Statistiques", style=discord.ButtonStyle.primary, row=0)
    async def stats(self, i: discord.Interaction, b):
        data = jload(F_DATA); bans = jload(F_BANS)
        gid = str(i.guild.id); custom = get_custom(i.guild.id)
        cfg = get_cfg(i.guild.id)
        nb_m = len(data.get(gid, {}))
        nb_b = len(bans.get(gid, []))
        nb_a = sum(len(v.get("historique", [])) for v in data.get(gid, {}).values())
        e = E(f"📊 Statistiques — {i.guild.name}", couleur=0x5865F2)
        e.set_thumbnail(url=i.guild.icon.url if i.guild.icon else None)
        e.add_field(name="👥 Membres avertis", value=f"```{nb_m}```", inline=True)
        e.add_field(name="🔨 Bannissements", value=f"```{nb_b}```", inline=True)
        e.add_field(name="⚠️ Total avert.", value=f"```{nb_a}```", inline=True)
        e.add_field(name="🚫 Mots filtrés", value=f"```{len(INSULTES_BASE)+len(custom)}```", inline=True)
        e.add_field(name="🔒 Lockdown", value=f"```{'Actif' if cfg.get('lockdown') else 'Inactif'}```", inline=True)
        e.add_field(name="🛡️ Anti-Raid", value=f"```{'Actif' if cfg.get('antiraid') else 'Inactif'}```", inline=True)
        e.add_field(name="🚫 Anti-Invite", value=f"```{'Actif' if cfg.get('anti_invite') else 'Inactif'}```", inline=True)
        e.add_field(name="⏱️ Expiration avert.", value="```5 mois```", inline=True)
        e.add_field(name="🔒 Seuil ban", value=f"```{MAX_AVERT} avert.```", inline=True)
        await i.response.send_message(embed=e, ephemeral=True)

    @discord.ui.button(label="🔨 Liste bans", style=discord.ButtonStyle.danger, row=0)
    async def bans(self, i: discord.Interaction, b):
        data = jload(F_BANS)
        liste = data.get(str(i.guild.id), [])
        e = E("🔨 Historique des bannissements", couleur=0xED4245)
        e.description = "\n".join([f"• **{x['pseudo']}** `{x['id']}` — {x.get('raison','?')} — {x['date']}" for x in liste[-15:]]) if liste else "*Aucun bannissement.*"
        e.set_footer(text=f"{len(liste)} ban(s) • ModBot")
        await i.response.send_message(embed=e, ephemeral=True)

# ═══════════════════════════════════════════
#  PANEL PRINCIPAL
# ═══════════════════════════════════════════

class VuePanel(discord.ui.View):
    def __init__(self): super().__init__(timeout=300)

    @discord.ui.button(label="🚫 Gestion Insultes", style=discord.ButtonStyle.danger, row=0)
    async def insultes(self, i: discord.Interaction, b):
        e = E("🚫 Gestion des insultes", "Ajoute, retire ou liste les mots filtrés.\nGère également les rôles immunisés.", 0xED4245)
        await i.response.send_message(embed=e, view=VuePanelInsultes(), ephemeral=True)

    @discord.ui.button(label="🛡️ Sécurité", style=discord.ButtonStyle.primary, row=0)
    async def securite(self, i: discord.Interaction, b):
        cfg = get_cfg(i.guild.id)
        e = E("🛡️ Paramètres de sécurité", "Gère le lockdown, l'anti-raid et l'anti-invite.", 0x5865F2)
        e.add_field(name="🔒 Lockdown", value="`Actif`" if cfg.get("lockdown") else "`Inactif`", inline=True)
        e.add_field(name="🛡️ Anti-Raid", value="`Actif`" if cfg.get("antiraid") else "`Inactif`", inline=True)
        e.add_field(name="🚫 Anti-Invite", value="`Actif`" if cfg.get("anti_invite") else "`Inactif`", inline=True)
        await i.response.send_message(embed=e, view=VuePanelSecurite(), ephemeral=True)

    @discord.ui.button(label="📌 Salons", style=discord.ButtonStyle.success, row=0)
    async def salons(self, i: discord.Interaction, b):
        e = E("📌 Configuration des salons", "Définis ou crée les salons utilisés par ModBot.", 0x43B581)
        await i.response.send_message(embed=e, view=VuePanelSalons(), ephemeral=True)

    @discord.ui.button(label="📊 Stats & Bans", style=discord.ButtonStyle.secondary, row=0)
    async def stats(self, i: discord.Interaction, b):
        e = E("📊 Statistiques & Bannissements", "Consulte les statistiques et la liste des bans.", 0x5865F2)
        await i.response.send_message(embed=e, view=VuePanelStats(), ephemeral=True)

    @discord.ui.button(label="ℹ️ Info bot", style=discord.ButtonStyle.secondary, row=1)
    async def info(self, i: discord.Interaction, b):
        import bot as bot_module
        custom = get_custom(i.guild.id)
        e = E("👮 ModBot — Informations", couleur=0x5865F2)
        e.set_thumbnail(url=bot_module.bot.user.display_avatar.url)
        e.add_field(name="🤖 Nom", value=str(bot_module.bot.user), inline=True)
        e.add_field(name="🆔 ID", value=f"`{bot_module.bot.user.id}`", inline=True)
        e.add_field(name="🌐 Serveurs", value=f"`{len(bot_module.bot.guilds)}`", inline=True)
        e.add_field(name="🚫 Mots filtrés", value=f"`{len(INSULTES_BASE)+len(custom)}`", inline=True)
        e.add_field(name="⚙️ Développé par", value="**gimskh.**", inline=True)
        await i.response.send_message(embed=e, ephemeral=True)
