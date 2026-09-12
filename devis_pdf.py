# -*- coding: utf-8 -*-
"""
Les documents en PDF : le devis avant la vente, la facture apres.

Le devis porte le logo, le numero, le client, le projet, le prix et le
lien pour payer. La facture porte l'identite du vendeur, le numero de la
suite legale, le detail, le total et la mention de TVA.

Ecrit a la main, sans aucune dependance : une page PDF n'a besoin que de
quelques objets. Les polices sont celles que tout lecteur PDF connait
(Helvetica), en codage WinAnsi — accents francais et symbole euro compris,
aucun fichier de police a embarquer. Le logo est un JPEG, que le format
sait afficher tel quel.
"""
import unicodedata
import zlib
from datetime import datetime, timezone

LARGEUR, HAUTEUR = 595.28, 841.89          # A4, en points
MARGE = 48

# Largeur des glyphes Helvetica, en milliemes de corps. Sert a couper les
# lignes au bon endroit : un texte qui deborde de la page ne se lit pas.
_HELVETICA = {
    " ": 278, "!": 278, '"': 355, "#": 556, "$": 556, "%": 889, "&": 667, "'": 191,
    "(": 333, ")": 333, "*": 389, "+": 584, ",": 278, "-": 333, ".": 278, "/": 278,
    ":": 278, ";": 278, "<": 584, "=": 584, ">": 584, "?": 556, "@": 1015,
    "A": 667, "B": 667, "C": 722, "D": 722, "E": 667, "F": 611, "G": 778, "H": 722,
    "I": 278, "J": 500, "K": 667, "L": 556, "M": 833, "N": 722, "O": 778, "P": 667,
    "Q": 778, "R": 722, "S": 667, "T": 611, "U": 722, "V": 667, "W": 944, "X": 667,
    "Y": 667, "Z": 611, "[": 278, "\\": 278, "]": 278, "^": 469, "_": 556, "`": 333,
    "a": 556, "b": 556, "c": 500, "d": 556, "e": 556, "f": 278, "g": 556, "h": 556,
    "i": 222, "j": 222, "k": 500, "l": 222, "m": 833, "n": 556, "o": 556, "p": 556,
    "q": 556, "r": 333, "s": 500, "t": 278, "u": 556, "v": 500, "w": 722, "x": 500,
    "y": 500, "z": 500, "{": 334, "|": 260, "}": 334, "~": 584,
    "€": 556, "«": 556, "»": 556, "—": 1000, "–": 556, "’": 222, "‘": 222,
    "“": 333, "”": 333, "…": 1000, "·": 278, "°": 400, "\u00a0": 278, "œ": 944,
    "Œ": 1000, "æ": 889, "Æ": 1000,
}
# Le gras est un peu plus large : on compte large, pour ne jamais deborder.
_GRAS = 1.08

COULEURS = {
    "nuit": (0.059, 0.075, 0.125),
    "or": (0.945, 0.769, 0.059),
    "or_fonce": (0.62, 0.45, 0.02),
    "encre": (0.10, 0.11, 0.14),
    "gris": (0.42, 0.45, 0.50),
    "clair": (0.86, 0.88, 0.92),
    "fond": (0.955, 0.96, 0.97),
    "creme": (1.0, 0.975, 0.89),
    "blanc": (1.0, 1.0, 1.0),
    "lien": (0.11, 0.30, 0.85),
}


def _largeur_car(caractere, gras=False):
    largeur = _HELVETICA.get(caractere)
    if largeur is None:
        base = unicodedata.normalize("NFD", caractere)[:1]
        largeur = _HELVETICA.get(base, 556)
    return largeur * (_GRAS if gras else 1.0)


def largeur(texte, taille, gras=False):
    """La largeur d'un texte, en points."""
    return sum(_largeur_car(c, gras) for c in str(texte)) * taille / 1000


def texte_winansi(texte):
    """
    Le texte en octets WinAnsi (cp1252). Ce qui n'y existe pas — un emoji,
    une lettre arabe — devient « ? » plutot que de casser le document.
    """
    propre = "".join(c for c in str(texte or "")
                     if unicodedata.category(c)[0] != "C")
    return propre.encode("cp1252", errors="replace")


def couper(texte, taille, largeur_max, gras=False):
    """Le texte en lignes qui tiennent dans `largeur_max` ; les paragraphes restent."""
    lignes = []
    for paragraphe in str(texte or "").replace("\r", "").split("\n"):
        mots = paragraphe.split()
        if not mots:
            lignes.append("")
            continue
        ligne = ""
        for mot in mots:
            # Un mot plus long que la ligne (une adresse, par exemple) est
            # coupe : il ne doit pas sortir de la page.
            while largeur(mot, taille, gras) > largeur_max:
                n = len(mot)
                while n > 1 and largeur(mot[:n], taille, gras) > largeur_max:
                    n -= 1
                if ligne:
                    lignes.append(ligne)
                    ligne = ""
                lignes.append(mot[:n])
                mot = mot[n:]
            if not mot:
                continue
            essai = f"{ligne} {mot}" if ligne else mot
            if largeur(essai, taille, gras) <= largeur_max:
                ligne = essai
            else:
                lignes.append(ligne)
                ligne = mot
        if ligne:
            lignes.append(ligne)
    return lignes


def borner(lignes, maximum):
    """Au plus `maximum` lignes ; la derniere dit qu'il y avait une suite."""
    if len(lignes) <= maximum:
        return lignes
    gardees = lignes[:maximum]
    gardees[-1] = gardees[-1].rstrip(" .,;:") + " …"
    return gardees


def dimensions_jpeg(octets):
    """(largeur, hauteur, composantes) d'un JPEG ; ValueError s'il n'en est pas un."""
    if not octets or octets[:2] != b"\xff\xd8":
        raise ValueError("pas un JPEG")
    i = 2
    while i + 9 < len(octets):
        if octets[i] != 0xFF:
            i += 1
            continue
        marqueur = octets[i + 1]
        if marqueur in (0xD8, 0x01) or 0xD0 <= marqueur <= 0xD7:
            i += 2
            continue
        longueur = int.from_bytes(octets[i + 2:i + 4], "big")
        if 0xC0 <= marqueur <= 0xCF and marqueur not in (0xC4, 0xC8, 0xCC):
            hauteur = int.from_bytes(octets[i + 5:i + 7], "big")
            largeur_px = int.from_bytes(octets[i + 7:i + 9], "big")
            composantes = octets[i + 9]
            if hauteur and largeur_px and composantes in (1, 3):
                return largeur_px, hauteur, composantes
            raise ValueError("JPEG illisible")
        i += 2 + longueur
    raise ValueError("JPEG sans dimensions")


def _chaine(octets):
    """Une chaine PDF litterale, echappee."""
    return (b"(" + octets.replace(b"\\", b"\\\\").replace(b"(", b"\\(")
            .replace(b")", b"\\)").replace(b"\r", b"\\r").replace(b"\n", b"\\n") + b")")


def _rgb(couleur):
    return " ".join(f"{c:.3f}" for c in couleur)


class _Page:
    """Les operations de dessin d'une page, dans l'ordre."""

    def __init__(self):
        self.ops = []
        self.liens = []

    def rect(self, x, y, l, h, couleur):
        self.ops.append(f"{_rgb(couleur)} rg {x:.2f} {y:.2f} {l:.2f} {h:.2f} re f".encode())

    def trait(self, x1, y1, x2, y2, couleur, epaisseur=0.8):
        self.ops.append(f"{_rgb(couleur)} RG {epaisseur:.2f} w {x1:.2f} {y1:.2f} m "
                        f"{x2:.2f} {y2:.2f} l S".encode())

    def texte(self, x, y, contenu, taille, couleur=COULEURS["encre"], gras=False, droite=False):
        if droite:
            x -= largeur(contenu, taille, gras)
        police = "/F2" if gras else "/F1"
        self.ops.append(f"BT {police} {taille:.1f} Tf {_rgb(couleur)} rg {x:.2f} {y:.2f} Td ".encode()
                        + _chaine(texte_winansi(contenu)) + b" Tj ET")

    def image(self, nom, x, y, l, h):
        self.ops.append(f"q {l:.2f} 0 0 {h:.2f} {x:.2f} {y:.2f} cm /{nom} Do Q".encode())

    def lien(self, x1, y1, x2, y2, adresse):
        self.liens.append(((x1, y1, x2, y2), adresse))

    def flux(self):
        return b"\n".join(self.ops)


def _assembler(objets):
    """
    Le fichier : en-tete, objets numerotes, table des positions (xref) et
    pied. La table doit etre exacte a l'octet pres — c'est elle qu'un lecteur
    PDF consulte en premier.
    """
    sortie = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    positions = []
    for numero, corps in enumerate(objets, 1):
        positions.append(len(sortie))
        sortie += f"{numero} 0 obj\n".encode() + corps + b"\nendobj\n"
    debut_xref = len(sortie)
    sortie += f"xref\n0 {len(objets) + 1}\n".encode() + b"0000000000 65535 f \n"
    for position in positions:
        sortie += f"{position:010d} 00000 n \n".encode()
    sortie += (f"trailer\n<< /Size {len(objets) + 1} /Root 1 0 R /Info {len(objets)} 0 R >>\n"
               f"startxref\n{debut_xref}\n%%EOF\n").encode()
    return bytes(sortie)


def _flux(donnees, entete=b""):
    compresse = zlib.compress(donnees, 9)
    return (b"<< " + entete + f"/Length {len(compresse)} /Filter /FlateDecode >>\nstream\n".encode()
            + compresse + b"\nendstream")


def _date_fr(iso, maintenant):
    try:
        moment = datetime.fromisoformat(str(iso))
    except (TypeError, ValueError):
        moment = maintenant
    return moment.strftime("%d/%m/%Y")


def nom_fichier(devis):
    return f"devis-{devis.get('id') or 'modbot'}.pdf"


def devis_pdf(devis, *, lien, categorie, prix_label, logo=None, maintenant=None,
              site="modbot-website.vercel.app"):
    """
    Le devis `devis` en PDF (octets).

    `categorie` et `prix_label` arrivent deja rediges (« 3 · Bot et site »,
    « 89,90 € ») : ce module dessine, il ne decide rien. `logo` est un JPEG
    facultatif ; sans lui, le devis reste complet.
    """
    maintenant = maintenant or datetime.now(timezone.utc)
    page = _Page()
    utile = LARGEUR - 2 * MARGE
    ident = str(devis.get("id") or "")

    # ── L'en-tete : la marque a gauche, « DEVIS » a droite ───────────
    page.rect(0, HAUTEUR - 120, LARGEUR, 120, COULEURS["nuit"])
    page.rect(0, HAUTEUR - 124, LARGEUR, 4, COULEURS["or"])
    image = None
    if logo:
        try:
            l_px, h_px, composantes = dimensions_jpeg(logo)
            image = (l_px, h_px, composantes)
        except ValueError:
            image = None
    x_marque = MARGE
    if image:
        page.image("Logo", MARGE, HAUTEUR - 96, 64, 64)
        x_marque = MARGE + 78
    page.texte(x_marque, HAUTEUR - 62, "ModBot", 24, COULEURS["blanc"], gras=True)
    page.texte(x_marque, HAUTEUR - 82, "Bots Discord et sites web sur mesure", 10, COULEURS["clair"])
    page.texte(LARGEUR - MARGE, HAUTEUR - 60, "DEVIS", 26, COULEURS["or"], gras=True, droite=True)
    page.texte(LARGEUR - MARGE, HAUTEUR - 80, f"N° {ident}", 11, COULEURS["blanc"], droite=True)
    page.texte(LARGEUR - MARGE, HAUTEUR - 96, f"Date : {maintenant.strftime('%d/%m/%Y')}", 10,
               COULEURS["clair"], droite=True)

    # ── Le client et l'objet ─────────────────────────────────────────
    y = HAUTEUR - 158
    colonne = LARGEUR / 2 + 10
    page.texte(MARGE, y, "CLIENT", 8.5, COULEURS["gris"], gras=True)
    page.texte(colonne, y, "OBJET", 8.5, COULEURS["gris"], gras=True)
    nom = str(devis.get("discord_nom") or devis.get("discord") or "—")
    page.texte(MARGE, y - 16, nom[:48], 12, gras=True)
    identifiant = str(devis.get("discord_id") or "")
    page.texte(MARGE, y - 31, f"Discord : {identifiant}" if identifiant else "Discord : pseudo communiqué",
               9.5, COULEURS["gris"])
    page.texte(colonne, y - 16, categorie, 12, gras=True)
    page.texte(colonne, y - 31, f"Demande reçue le {_date_fr(devis.get('creee_le'), maintenant)}",
               9.5, COULEURS["gris"])

    # ── Le projet, tel que le client l'a decrit ─────────────────────
    y -= 62
    page.texte(MARGE, y, "DESCRIPTION DU PROJET", 8.5, COULEURS["gris"], gras=True)
    y -= 16
    for ligne in borner(couper(devis.get("description"), 10.5, utile), 15):
        page.texte(MARGE, y, ligne, 10.5)
        y -= 14

    # ── Le prix ──────────────────────────────────────────────────────
    y -= 14
    page.rect(MARGE, y - 6, utile, 24, COULEURS["fond"])
    page.texte(MARGE + 10, y + 2, "Désignation", 9.5, COULEURS["gris"], gras=True)
    page.texte(LARGEUR - MARGE - 10, y + 2, "Montant", 9.5, COULEURS["gris"], gras=True, droite=True)
    y -= 26
    designation = borner(couper(f"Création sur mesure — {categorie}", 11, utile - 150), 2)
    for i, ligne in enumerate(designation):
        page.texte(MARGE + 10, y - i * 14, ligne, 11)
    page.texte(LARGEUR - MARGE - 10, y, prix_label, 11, droite=True)
    y -= 14 * len(designation) + 4
    page.trait(MARGE, y, LARGEUR - MARGE, y, COULEURS["clair"])
    y -= 22
    page.texte(LARGEUR - MARGE - 130, y, "Total TTC", 12, gras=True)
    page.texte(LARGEUR - MARGE - 10, y, prix_label, 15, COULEURS["or_fonce"], gras=True, droite=True)
    y -= 16
    page.texte(LARGEUR - MARGE - 10, y, "Payable en une fois, par carte bancaire ou PayPal.", 8.5,
               COULEURS["gris"], droite=True)

    # ── Le mot de l'equipe ───────────────────────────────────────────
    message = str(devis.get("message_prix") or "").strip()
    if message:
        y -= 30
        page.texte(MARGE, y, "LE MOT DE L'ÉQUIPE", 8.5, COULEURS["gris"], gras=True)
        y -= 16
        for ligne in borner(couper(message, 10.5, utile), 6):
            page.texte(MARGE, y, ligne, 10.5)
            y -= 14

    # ── Accepter et payer : le lien, cliquable ───────────────────────
    lignes_lien = borner(couper(lien, 9, utile - 28), 3)
    hauteur_boite = 52 + 12 * len(lignes_lien)
    y -= 22 + hauteur_boite
    y = max(y, 96)
    page.rect(MARGE, y, utile, hauteur_boite, COULEURS["creme"])
    page.rect(MARGE, y, 4, hauteur_boite, COULEURS["or"])
    haut = y + hauteur_boite
    page.texte(MARGE + 16, haut - 20, "Pour accepter ce devis et payer", 11.5, gras=True)
    for i, ligne in enumerate(lignes_lien):
        page.texte(MARGE + 16, haut - 36 - i * 12, ligne, 9, COULEURS["lien"])
    bas_lien = haut - 36 - (len(lignes_lien) - 1) * 12 - 3
    page.lien(MARGE + 12, bas_lien, LARGEUR - MARGE - 8, haut - 26, lien)
    page.texte(MARGE + 16, y + 10, "Paiement sécurisé par Stripe. ModBot ne voit jamais tes données bancaires.",
               8.5, COULEURS["gris"])

    # ── Le pied ──────────────────────────────────────────────────────
    page.trait(MARGE, 62, LARGEUR - MARGE, 62, COULEURS["clair"])
    page.texte(MARGE, 48, f"ModBot — {site}", 8.5, COULEURS["gris"], gras=True)
    pied = (f"Prix TTC. Le travail commence après le paiement, selon les conditions de la boutique : "
            f"{site}/conditions.html#boutique")
    for i, ligne in enumerate(borner(couper(pied, 8, utile), 2)):
        page.texte(MARGE, 36 - i * 10, ligne, 8, COULEURS["gris"])

    return _fichier(page, logo, image, f"Devis {ident}", maintenant)


def _fichier(page, logo, image, titre_pdf, maintenant):
    """
    Les objets du PDF, assembles : catalogue, pages, page, polices, image,
    contenu, liens, informations.

    Le devis et la facture dessinent des choses differentes mais
    produisent le meme genre de fichier : cette part-la n'a aucune raison
    d'exister en deux exemplaires.
    """
    objets = [None, None, None]         # 1 catalogue, 2 pages, 3 page
    polices = []
    for nom_police in ("Helvetica", "Helvetica-Bold"):
        objets.append(f"<< /Type /Font /Subtype /Type1 /BaseFont /{nom_police} "
                      f"/Encoding /WinAnsiEncoding >>".encode())
        polices.append(len(objets))
    ressources = f"/Font << /F1 {polices[0]} 0 R /F2 {polices[1]} 0 R >>"
    if image:
        l_px, h_px, composantes = image
        espace = "/DeviceRGB" if composantes == 3 else "/DeviceGray"
        objets.append(f"<< /Type /XObject /Subtype /Image /Width {l_px} /Height {h_px} "
                      f"/ColorSpace {espace} /BitsPerComponent 8 /Filter /DCTDecode "
                      f"/Length {len(logo)} >>\nstream\n".encode() + logo + b"\nendstream")
        ressources += f" /XObject << /Logo {len(objets)} 0 R >>"
    objets.append(_flux(page.flux()))
    contenu = len(objets)
    annotations = []
    for (x1, y1, x2, y2), adresse in page.liens:
        uri = _chaine(str(adresse).encode("ascii", errors="ignore"))
        objets.append(f"<< /Type /Annot /Subtype /Link /Rect [{x1:.2f} {y1:.2f} {x2:.2f} {y2:.2f}] "
                      f"/Border [0 0 0] /A << /S /URI /URI ".encode() + uri + b" >> >>")
        annotations.append(f"{len(objets)} 0 R")
    horodatage = maintenant.strftime("D:%Y%m%d%H%M%SZ")
    objets.append(b"<< /Title " + _chaine(texte_winansi(titre_pdf)) +
                  b" /Author (ModBot) /Producer (ModBot) /CreationDate " +
                  _chaine(horodatage.encode()) + b" >>")
    objets[0] = b"<< /Type /Catalog /Pages 2 0 R >>"
    objets[1] = b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>"
    objets[2] = (f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {LARGEUR} {HAUTEUR}] "
                 f"/Resources << {ressources} >> /Contents {contenu} 0 R "
                 f"/Annots [{' '.join(annotations)}] >>").encode()
    return _assembler(objets)


def _logo_lisible(logo):
    """Les dimensions du JPEG, ou None si ce n'en est pas un."""
    if not logo:
        return None
    try:
        return dimensions_jpeg(logo)
    except ValueError:
        return None


def nom_fichier_facture(facture):
    return f"facture-{(facture or {}).get('numero') or 'modbot'}.pdf"


def facture_pdf(facture, *, identite, tva, logo=None, maintenant=None,
                site="modbot-website.vercel.app"):
    """
    La facture `facture` en PDF (octets).

    `identite` est la liste des lignes du vendeur, deja redigees, et `tva`
    la mention de franchise : ce module dessine, il ne decide de rien — et
    surtout pas de ce qu'on a le droit d'ecrire sur une facture.
    """
    maintenant = maintenant or datetime.now(timezone.utc)
    facture = facture or {}
    page = _Page()
    utile = LARGEUR - 2 * MARGE
    numero = str(facture.get("numero") or "")
    image = _logo_lisible(logo)

    # ── L'en-tete : la marque a gauche, « FACTURE » a droite ─────────
    page.rect(0, HAUTEUR - 120, LARGEUR, 120, COULEURS["nuit"])
    page.rect(0, HAUTEUR - 124, LARGEUR, 4, COULEURS["or"])
    x_marque = MARGE
    if image:
        page.image("Logo", MARGE, HAUTEUR - 96, 64, 64)
        x_marque = MARGE + 78
    page.texte(x_marque, HAUTEUR - 62, "ModBot", 24, COULEURS["blanc"], gras=True)
    page.texte(x_marque, HAUTEUR - 82, "Bots Discord et sites web sur mesure", 10,
               COULEURS["clair"])
    page.texte(LARGEUR - MARGE, HAUTEUR - 60, "FACTURE", 26, COULEURS["or"],
               gras=True, droite=True)
    page.texte(LARGEUR - MARGE, HAUTEUR - 80, f"N° {numero}", 11, COULEURS["blanc"],
               droite=True)
    page.texte(LARGEUR - MARGE, HAUTEUR - 96,
               f"Émise le {_date_fr(facture.get('emise_le'), maintenant)}", 10,
               COULEURS["clair"], droite=True)

    # ── Qui vend, qui achete ─────────────────────────────────────────
    y = HAUTEUR - 158
    colonne = LARGEUR / 2 + 10
    page.texte(MARGE, y, "VENDEUR", 8.5, COULEURS["gris"], gras=True)
    page.texte(colonne, y, "CLIENT", 8.5, COULEURS["gris"], gras=True)
    lignes = borner([str(l) for l in (identite or []) if str(l).strip()], 6)
    for i, ligne in enumerate(lignes):
        page.texte(MARGE, y - 16 - i * 13, ligne, 11 if i == 0 else 9.5,
                   COULEURS["encre"] if i == 0 else COULEURS["gris"], gras=(i == 0))
    client = str(facture.get("client") or "—")
    page.texte(colonne, y - 16, client[:48], 11, gras=True)
    identifiant = str(facture.get("client_id") or "")
    page.texte(colonne, y - 29,
               f"Discord : {identifiant}" if identifiant else "Discord : pseudo communiqué",
               9.5, COULEURS["gris"])
    courriel = str(facture.get("email") or "")
    if courriel:
        page.texte(colonne, y - 42, courriel[:48], 9.5, COULEURS["gris"])

    # ── Le detail ────────────────────────────────────────────────────
    y -= 16 + 13 * max(len(lignes), 4) + 16
    page.rect(MARGE, y - 6, utile, 24, COULEURS["fond"])
    page.texte(MARGE + 10, y + 2, "Désignation", 9.5, COULEURS["gris"], gras=True)
    page.texte(LARGEUR - MARGE - 10, y + 2, "Montant", 9.5, COULEURS["gris"],
               gras=True, droite=True)
    y -= 26
    # Huit lignes au plus : une facture qui deborde de la page ne se lit
    # pas, et « borner » ne sait couper que du texte.
    for element in list(facture.get("lignes") or [])[:8]:
        if not isinstance(element, dict):
            continue
        titres = borner(couper(element.get("libelle"), 11, utile - 150), 2)
        for i, ligne in enumerate(titres):
            page.texte(MARGE + 10, y - i * 14, ligne, 11)
        page.texte(LARGEUR - MARGE - 10, y,
                   _prix(element.get("montant")), 11, droite=True)
        y -= 14 * max(len(titres), 1) + 6

    y -= 4
    page.trait(MARGE, y, LARGEUR - MARGE, y, COULEURS["clair"])
    y -= 22
    page.texte(LARGEUR - MARGE - 150, y, "Total TTC", 12, gras=True)
    page.texte(LARGEUR - MARGE - 10, y, _prix(facture.get("montant")), 15,
               COULEURS["or_fonce"], gras=True, droite=True)
    y -= 15
    page.texte(LARGEUR - MARGE - 10, y, tva, 8.5, COULEURS["gris"], droite=True)

    # ── Le paiement, deja fait ───────────────────────────────────────
    y -= 34
    hauteur_boite = 62
    y = max(y - hauteur_boite, 96)
    page.rect(MARGE, y, utile, hauteur_boite, COULEURS["creme"])
    page.rect(MARGE, y, 4, hauteur_boite, COULEURS["or"])
    haut = y + hauteur_boite
    page.texte(MARGE + 16, haut - 20, "Payée", 11.5, gras=True)
    page.texte(MARGE + 16, haut - 36,
               f"Le {_date_fr(facture.get('payee_le'), maintenant)} "
               f"par {facture.get('moyen') or 'carte bancaire'}.", 9.5, COULEURS["gris"])
    page.texte(MARGE + 16, haut - 50,
               f"Commande n° {facture.get('commande') or '—'}", 9.5, COULEURS["gris"])

    # ── Le pied ──────────────────────────────────────────────────────
    page.trait(MARGE, 62, LARGEUR - MARGE, 62, COULEURS["clair"])
    page.texte(MARGE, 48, f"ModBot — {site}", 8.5, COULEURS["gris"], gras=True)
    pied = ("Facture acquittée, à conserver. Conditions de vente et droit de "
            f"rétractation : {site}/conditions.html#boutique — mentions légales : "
            f"{site}/mentions.html")
    for i, ligne in enumerate(borner(couper(pied, 8, utile), 2)):
        page.texte(MARGE, 36 - i * 10, ligne, 8, COULEURS["gris"])

    return _fichier(page, logo, image, f"Facture {numero}", maintenant)


def _prix(centimes):
    """3900 → « 39 € », 399 → « 3,99 € ». Le meme rendu que la boutique."""
    centimes = int(centimes or 0)
    euros, reste = divmod(centimes, 100)
    return f"{euros} €" if not reste else f"{euros},{reste:02d} €"
