import json
import os
from pathlib import Path

import requests

GRAMMES_PAR_ONCE = 31.1035
FICHIER_ETAT = Path("etat.json")

NTFY_TOPIC = os.environ["NTFY_TOPIC"]

# Alerte quand le cours est SOUS un de ces niveaux (EUR par gramme)
NIVEAUX_BAISSE = [114, 115, 116,117, 118]

# Alerte quand le cours est AU-DESSUS d'un de ces niveaux (vide = aucune)
NIVEAUX_HAUSSE = [119, 120, 121]

# Écart à ajouter au prix du script pour l'aligner sur ton site (en EUR/g).
# Exemple : si ton site affiche 0,20 de moins que le script, mets -0.20
AJUSTEMENT_EUR_G = 0.0

# Un niveau déjà déclenché se réarme quand le cours s'en éloigne de cette marge (EUR/g)
MARGE_REARMEMENT = 0.30


def prix_or_gramme_eur():
    r = requests.get("https://api.gold-api.com/price/XAU", timeout=15)
    r.raise_for_status()
    usd_once = float(r.json()["price"])

    r = requests.get("https://api.frankfurter.app/latest?from=USD&to=EUR", timeout=15)
    r.raise_for_status()
    eur_once = usd_once * float(r.json()["rates"]["EUR"])

    return eur_once / GRAMMES_PAR_ONCE


def notifier(titre, message):
    requests.post(
        f"https://ntfy.sh/{NTFY_TOPIC}",
        data=message.encode("utf-8"),
        headers={"Title": titre.encode("utf-8"), "Priority": "high", "Tags": "moneybag"},
        timeout=15,
    ).raise_for_status()


def main():
    etat = {"desarme": {}}
    if FICHIER_ETAT.exists():
        try:
            etat.update(json.loads(FICHIER_ETAT.read_text()))
        except ValueError:
            pass
    desarme = etat.setdefault("desarme", {})

    prix = prix_or_gramme_eur() + AJUSTEMENT_EUR_G
    print(f"Or : {prix:.2f} EUR/g")

    lignes = []

    for niveau in sorted(NIVEAUX_BAISSE, reverse=True):
        cle = f"baisse_{niveau}"
        if prix <= niveau and not desarme.get(cle):
            lignes.append(f"⬇️ Sous {niveau} EUR/g")
            desarme[cle] = True
        elif prix > niveau + MARGE_REARMEMENT:
            desarme[cle] = False

    for niveau in sorted(NIVEAUX_HAUSSE):
        cle = f"hausse_{niveau}"
        if prix >= niveau and not desarme.get(cle):
            lignes.append(f"⬆️ Au-dessus de {niveau} EUR/g")
            desarme[cle] = True
        elif prix < niveau - MARGE_REARMEMENT:
            desarme[cle] = False

    if lignes:
        notifier("Or : niveau atteint", "\n".join(lignes) + f"\nCours actuel : {prix:.2f} EUR/g")

    FICHIER_ETAT.write_text(json.dumps(etat))


if __name__ == "__main__":
    main()
