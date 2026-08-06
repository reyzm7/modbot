"""
Suite de tests du noyau de securite ModBot.

Lancement :
    python -m unittest test_security -v
    python test_security.py

Ne necessite ni token Discord ni connexion reseau.
"""

import os
import shutil
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

import security_core as sc


# Liste de mots utilisee par les tests de detection
MOTS = [
    "tg", "fdp", "pd", "ntm", "connard", "connasse", "salope", "pute",
    "batard", "encule", "fils de pute", "niquer", "ta gueule", "putain",
    "abruti", "imbecile", "cretin", "bouffon", "trou du cul", "enfoire",
    "ordure", "dechet", "nique ta mere", "ta race",
]


class TestNormalisation(unittest.TestCase):
    """La normalisation doit ramener toutes les variantes au meme texte."""

    def test_accents_et_casse(self):
        self.assertEqual(sc.normalize_text("ÉCOLE Été"), "ecole ete")

    def test_pleine_largeur(self):
        self.assertEqual(sc.normalize_text("ＳＡＬＯＰＥ"), "salope")

    def test_caracteres_invisibles(self):
        # zero-width space insere entre chaque lettre
        texte = "s​a​l​o​p​e"
        self.assertEqual(sc.normalize_text(texte), "salope")

    def test_symboles(self):
        self.assertEqual(sc.normalize_text("s@l0pe"), "salope")

    def test_cyrillique(self):
        # 'а' et 'о' sont cyrilliques, visuellement identiques au latin
        self.assertEqual(sc.normalize_text("sаlоpe"), "salope")

    def test_chiffres_conserves_sans_leet(self):
        self.assertEqual(sc.normalize_text("79", leet=False), "79")
        self.assertEqual(sc.normalize_text("79", leet=True), "tg")

    def test_longueur_bornee(self):
        self.assertLessEqual(len(sc.normalize_text("a" * 10000)), sc.MAX_SCAN_LENGTH)


class TestDetectionContournements(unittest.TestCase):
    """Chaque technique de contournement doit etre attrapee."""

    CAS = [
        ("separateurs espaces", "s a l o p e"),
        ("separateurs points", "s.a.l.o.p.e"),
        ("separateurs tirets", "s-a-l-o-p-e"),
        ("separateurs underscores", "s_a_l_o_p_e"),
        ("symbole arobase", "s@lope"),
        ("leet speak", "s4l0pe"),
        ("leet long", "espece de c0nn4rd"),
        ("majuscules", "SALOPE"),
        ("lettres repetees", "saaaalope"),
        ("markdown gras", "**salope**"),
        ("cyrillique", "sаlope"),
        ("pleine largeur", "ｓａｌｏｐｅ"),
        ("insulte dans une phrase", "tu es une s a l o p e de merde"),
        ("expression multi-mots", "ta gueule"),
        ("expression espacee", "t a  g u e u l e"),
        ("sigle court", "tg"),
        ("sigle avec ponctuation", "TG !"),
        ("accent", "enculé"),
        ("expression longue", "nique ta mere"),
        ("zero-width", "s​a​l​o​p​e"),
    ]

    def test_contournements_detectes(self):
        for nom, texte in self.CAS:
            with self.subTest(technique=nom, texte=texte):
                resultat = sc.detect_bad_word(texte, MOTS)
                self.assertIsNotNone(resultat, f"non detecte : {texte!r}")


class TestFauxPositifs(unittest.TestCase):
    """Aucun texte legitime ne doit declencher de sanction."""

    CAS = [
        "dispute", "ils se disputent",
        "la réputation du serveur", "le député a parlé",
        "calcul de la culture", "je fais un calcul",
        "salon général", "bienvenue dans le salon",
        "salopette bleue", "salut tout le monde",
        "concert de musique unique", "la connexion est rapide",
        "le TGV part a 8h", "un fichier pdf",
        "seconde connexion au serveur", "particulier",
        "update speed rapide", "il y a 79 membres",
        "on est en 2005", "le score est 1337",
        "bonjour tout le monde ça va ?", "j'ai 18 ans",
        "reponse dans 30 minutes", "technique de configuration",
        "ce vehicule est ridicule", "contact le conseiller",
        "analyse des statistiques", "https://discord.gg/abcdef",
        "reconnaissance vocale", "un bacon dans le balcon",
    ]

    def test_aucun_faux_positif(self):
        for texte in self.CAS:
            with self.subTest(texte=texte):
                resultat = sc.detect_bad_word(texte, MOTS)
                self.assertIsNone(
                    resultat,
                    f"faux positif sur {texte!r} -> {resultat}",
                )

    def test_liste_blanche_personnalisee(self):
        # Un serveur nomme "Les Putes de Paris" ne doit pas s'auto-sanctionner
        self.assertIsNotNone(sc.detect_bad_word("pute", MOTS))
        self.assertIsNone(sc.detect_bad_word("pute", MOTS, extra_safe=["pute"]))


class TestEchelleSanctions(unittest.TestCase):

    def test_paliers_par_defaut(self):
        self.assertEqual(sc.resolve_sanction(1)["action"], "warn")
        self.assertEqual(sc.resolve_sanction(2)["action"], "mute")
        self.assertEqual(sc.resolve_sanction(4)["action"], "kick")
        self.assertEqual(sc.resolve_sanction(5)["action"], "ban")
        self.assertEqual(sc.resolve_sanction(99)["action"], "ban")

    def test_points_sous_le_premier_palier(self):
        self.assertEqual(sc.resolve_sanction(0)["action"], "warn")

    def test_normalisation_entree_invalide(self):
        ladder = sc.normalize_ladder("pas une liste")
        self.assertEqual(len(ladder), len(sc.DEFAULT_SANCTION_LADDER))

        ladder = sc.normalize_ladder([{"threshold": "abc", "action": "explode"}])
        self.assertEqual(len(ladder), len(sc.DEFAULT_SANCTION_LADDER))

    def test_action_inconnue_devient_warn(self):
        ladder = sc.normalize_ladder([{"threshold": 1, "action": "explode"}])
        self.assertEqual(ladder[0]["action"], "warn")

    def test_timeout_borne_a_28_jours(self):
        ladder = sc.normalize_ladder([{"threshold": 1, "action": "mute", "minutes": 999999}])
        self.assertLessEqual(ladder[0]["minutes"], 28 * 24 * 60)

    def test_tri_des_paliers(self):
        ladder = sc.normalize_ladder([
            {"threshold": 5, "action": "ban"},
            {"threshold": 1, "action": "warn"},
        ])
        self.assertEqual([s["threshold"] for s in ladder], [1, 5])


class TestHistoriqueInfractions(unittest.TestCase):

    def setUp(self):
        self.dossier = tempfile.mkdtemp()
        self.store = sc.InfractionStore(os.path.join(self.dossier, "inf.json"))

    def tearDown(self):
        shutil.rmtree(self.dossier, ignore_errors=True)

    def test_cumul_des_points(self):
        total, _ = self.store.add("1", "42", "insulte", points=1)
        self.assertEqual(total, 1)
        total, _ = self.store.add("1", "42", "insulte grave", points=3)
        self.assertEqual(total, 4)

    def test_isolation_par_serveur(self):
        self.store.add("1", "42", "insulte")
        self.assertEqual(self.store.points("2", "42"), 0)

    def test_reinitialisation(self):
        self.store.add("1", "42", "insulte")
        self.assertTrue(self.store.reset("1", "42"))
        self.assertEqual(self.store.points("1", "42"), 0)
        self.assertFalse(self.store.reset("1", "42"))

    def test_purge_des_anciennes_entrees(self):
        store = sc.InfractionStore(os.path.join(self.dossier, "vieux.json"), retention_days=30)
        store.add("1", "42", "recente")
        # Injecte une entree vieille de 60 jours
        data = store._load()
        vieille = (datetime.now(timezone.utc) - timedelta(days=60)).isoformat()
        data["1"]["42"].insert(0, {"date": vieille, "reason": "ancienne", "points": 5})
        store._save(data)
        self.assertEqual(store.points("1", "42"), 1)  # l'ancienne est ignoree

    def test_borne_par_membre(self):
        for i in range(150):
            self.store.add("1", "42", f"infraction {i}")
        self.assertLessEqual(len(self.store.history("1", "42")),
                             sc.InfractionStore.MAX_ENTRIES_PER_MEMBER)

    def test_fichier_corrompu_tolere(self):
        chemin = os.path.join(self.dossier, "casse.json")
        with open(chemin, "w", encoding="utf-8") as fp:
            fp.write("{ ceci n'est pas du json")
        store = sc.InfractionStore(chemin)
        self.assertEqual(store.points("1", "42"), 0)

    def test_classement_serveur(self):
        self.store.add("1", "10", "a", points=1)
        self.store.add("1", "20", "b", points=5)
        classement = self.store.guild_summary("1")
        self.assertEqual(classement[0]["user_id"], "20")


class TestAntiRaid(unittest.TestCase):

    def test_rafale_detectee(self):
        detecteur = sc.RaidDetector()
        cfg = {"join_threshold": 5, "join_window": 10}
        resultats = [detecteur.register_join("1", cfg) for _ in range(5)]
        self.assertFalse(resultats[3]["burst"])
        self.assertTrue(resultats[4]["burst"])

    def test_serveurs_independants(self):
        detecteur = sc.RaidDetector()
        cfg = {"join_threshold": 3, "join_window": 10}
        for _ in range(3):
            detecteur.register_join("1", cfg)
        self.assertFalse(detecteur.register_join("2", cfg)["burst"])

    def test_mode_securite(self):
        detecteur = sc.RaidDetector()
        self.assertFalse(detecteur.safe_mode_active("1"))
        detecteur.engage_safe_mode("1", minutes=5)
        self.assertTrue(detecteur.safe_mode_active("1"))
        self.assertTrue(detecteur.release_safe_mode("1"))
        self.assertFalse(detecteur.safe_mode_active("1"))

    def test_compte_neuf_suspect(self):
        risque = sc.account_risk(datetime.now(timezone.utc), has_avatar=False)
        self.assertTrue(risque["suspicious"])
        self.assertGreaterEqual(risque["score"], 50)

    def test_compte_ancien_sain(self):
        vieux = datetime.now(timezone.utc) - timedelta(days=400)
        risque = sc.account_risk(vieux, has_avatar=True)
        self.assertFalse(risque["suspicious"])
        self.assertEqual(risque["score"], 0)

    def test_date_naive_acceptee(self):
        naive = datetime.now() - timedelta(days=400)
        risque = sc.account_risk(naive, has_avatar=True)
        self.assertFalse(risque["suspicious"])


class TestAntiNuke(unittest.TestCase):

    def test_seuil_declenche_une_seule_fois(self):
        garde = sc.NukeGuard()
        resultats = [garde.register("1", "99", "channel_delete") for _ in range(6)]
        declenchements = [r for r in resultats if r["tripped"]]
        self.assertEqual(len(declenchements), 1, "l'alerte doit etre unique par rafale")

    def test_acteurs_independants(self):
        garde = sc.NukeGuard()
        for _ in range(3):
            garde.register("1", "99", "channel_delete")
        self.assertFalse(garde.register("1", "77", "channel_delete")["tripped"])

    def test_seuil_personnalise(self):
        garde = sc.NukeGuard()
        limites = {"channel_delete": {"limit": 2, "window": 20}}
        self.assertFalse(garde.register("1", "99", "channel_delete", limites)["tripped"])
        self.assertTrue(garde.register("1", "99", "channel_delete", limites)["tripped"])

    def test_liste_blanche(self):
        cfg = {"whitelist_users": ["123"], "whitelist_roles": ["456"]}
        self.assertTrue(sc.is_whitelisted("123", [], None, None, cfg))
        self.assertTrue(sc.is_whitelisted("999", ["456"], None, None, cfg))
        self.assertFalse(sc.is_whitelisted("999", ["888"], None, None, cfg))

    def test_proprietaire_et_bot_de_confiance(self):
        self.assertTrue(sc.is_whitelisted("500", [], "500", None, {}))
        self.assertTrue(sc.is_whitelisted("600", [], None, "600", {}))
        self.assertFalse(sc.is_whitelisted("500", [], "500", None, {"trust_owner": False}))


class TestSauvegardes(unittest.TestCase):

    def setUp(self):
        self.dossier = tempfile.mkdtemp()
        self.store = sc.BackupStore(self.dossier, max_per_guild=3)
        self.snapshot = {
            "roles": [{"name": "Admin"}],
            "categories": [{"name": "Texte"}],
            "channels": [{"name": "general"}, {"name": "logs"}],
        }

    def tearDown(self):
        shutil.rmtree(self.dossier, ignore_errors=True)

    def test_creation_et_lecture(self):
        entree = self.store.create("1", self.snapshot, author="Test", note="essai")
        self.assertEqual(entree["counts"]["channels"], 2)
        self.assertEqual(entree["counts"]["roles"], 1)
        recharge = self.store.get("1", entree["id"])
        self.assertEqual(recharge["note"], "essai")

    def test_liste_sans_contenu(self):
        self.store.create("1", self.snapshot)
        meta = self.store.list("1")
        self.assertNotIn("data", meta[0], "la liste ne doit pas transporter le contenu")

    def test_rotation(self):
        for i in range(5):
            self.store.create("1", self.snapshot, note=f"n{i}")
        self.assertEqual(len(self.store.list("1")), 3)

    def test_suppression(self):
        entree = self.store.create("1", self.snapshot)
        self.assertTrue(self.store.delete("1", entree["id"]))
        self.assertFalse(self.store.delete("1", entree["id"]))

    def test_identifiant_invalide_refuse(self):
        self.store.create("1", self.snapshot)
        self.assertIsNone(self.store.get("1", "../../etc/passwd"))
        self.assertIsNone(self.store.get("1", ""))

    def test_isolation_par_serveur(self):
        self.store.create("1", self.snapshot)
        self.assertEqual(self.store.list("2"), [])


class TestCaptcha(unittest.TestCase):

    def setUp(self):
        self.dossier = tempfile.mkdtemp()
        self.chemin = os.path.join(self.dossier, "captcha.json")
        self.store = sc.CaptchaStore(self.chemin, ttl_minutes=10, max_attempts=3)

    def tearDown(self):
        shutil.rmtree(self.dossier, ignore_errors=True)

    def test_alphabet_sans_caracteres_ambigus(self):
        for ambigu in "OIL0125SZ":
            self.assertNotIn(ambigu, sc.CAPTCHA_ALPHABET,
                             f"« {ambigu} » preterait a confusion sur une image")

    def test_code_longueur_et_alphabet(self):
        code = sc.generate_captcha_code(5)
        self.assertEqual(len(code), 5)
        self.assertTrue(all(c in sc.CAPTCHA_ALPHABET for c in code))

    def test_codes_differents(self):
        codes = {sc.generate_captcha_code() for _ in range(50)}
        self.assertGreater(len(codes), 40, "les codes doivent etre aleatoires")

    def test_verification_reussie(self):
        code = self.store.issue("1", "42", role_id="777")
        res = self.store.verify("1", "42", code)
        self.assertEqual(res["status"], "ok")
        self.assertEqual(res["role_id"], "777")

    def test_tolerance_casse_et_espaces(self):
        code = self.store.issue("1", "42")
        self.assertEqual(self.store.verify("1", "42", f"  {code.lower()} ")["status"], "ok")

    def test_code_consomme_apres_succes(self):
        code = self.store.issue("1", "42")
        self.store.verify("1", "42", code)
        self.assertEqual(self.store.verify("1", "42", code)["status"], "absent")

    def test_mauvais_code_decompte_les_essais(self):
        self.store.issue("1", "42")
        self.assertEqual(self.store.verify("1", "42", "ZZZZZ")["remaining"], 2)
        self.assertEqual(self.store.verify("1", "42", "ZZZZZ")["remaining"], 1)
        self.assertEqual(self.store.verify("1", "42", "ZZZZZ")["status"], "bloque")

    def test_bloque_efface_la_verification(self):
        code = self.store.issue("1", "42")
        for _ in range(3):
            self.store.verify("1", "42", "ZZZZZ")
        # meme le bon code ne passe plus : il faut en redemander un
        self.assertEqual(self.store.verify("1", "42", code)["status"], "absent")

    def test_expiration(self):
        store = sc.CaptchaStore(self.chemin, ttl_minutes=-1)
        code = store.issue("1", "42")
        self.assertEqual(store.verify("1", "42", code)["status"], "expire")

    def test_persistance_sur_disque(self):
        """Un redemarrage ne doit pas annuler les verifications en cours."""
        code = self.store.issue("1", "42", role_id="777")
        autre = sc.CaptchaStore(self.chemin)  # simule un redemarrage du bot
        self.assertEqual(autre.verify("1", "42", code)["status"], "ok")

    def test_isolation_par_serveur(self):
        code = self.store.issue("1", "42")
        self.assertEqual(self.store.verify("2", "42", code)["status"], "absent")

    def test_nouveau_code_remplace_l_ancien(self):
        ancien = self.store.issue("1", "42")
        nouveau = self.store.issue("1", "42")
        if ancien != nouveau:
            self.assertEqual(self.store.verify("1", "42", ancien)["status"], "faux")

    def test_compteur_en_attente(self):
        self.store.issue("1", "42")
        self.store.issue("1", "43")
        self.assertEqual(self.store.pending("1"), 2)
        self.store.clear("1", "42")
        self.assertEqual(self.store.pending("1"), 1)
        self.store.clear("1")
        self.assertEqual(self.store.pending("1"), 0)

    def test_purge_des_expires(self):
        sc.CaptchaStore(self.chemin, ttl_minutes=-1).issue("1", "42")
        self.assertEqual(self.store.purge_expired(), 1)
        self.assertEqual(self.store.purge_expired(), 0)

    def test_purge_epargne_les_valides(self):
        code = self.store.issue("1", "42")
        self.store.purge_expired()
        self.assertEqual(self.store.verify("1", "42", code)["status"], "ok")

    def test_fichier_corrompu_ne_casse_rien(self):
        with open(self.chemin, "w", encoding="utf-8") as fp:
            fp.write("{ ceci n'est pas du json")
        self.assertEqual(self.store.verify("1", "42", "ABCDE")["status"], "absent")
        self.assertTrue(self.store.issue("1", "42"))


class TestUtilitaires(unittest.TestCase):

    def test_parse_iso_formats(self):
        self.assertIsNotNone(sc.parse_iso("2026-01-15T10:30:00+00:00"))
        self.assertIsNotNone(sc.parse_iso("2026-01-15 10:30:00"))
        self.assertIsNotNone(sc.parse_iso("15/01/2026 10:30"))
        self.assertIsNone(sc.parse_iso("n'importe quoi"))
        self.assertIsNone(sc.parse_iso(None))

    def test_parse_iso_rend_aware(self):
        self.assertIsNotNone(sc.parse_iso("2026-01-15 10:30:00").tzinfo)

    def test_duree_lisible(self):
        self.assertEqual(sc.human_duration(30), "30 min")
        self.assertEqual(sc.human_duration(60), "1 heure")
        self.assertEqual(sc.human_duration(120), "2 heures")
        self.assertEqual(sc.human_duration(1440), "1 jour")
        self.assertEqual(sc.human_duration(0), "-")


if __name__ == "__main__":
    unittest.main(verbosity=2)
