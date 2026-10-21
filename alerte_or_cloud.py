import json
import os
import time
from pathlib import Path

import requests

GRAMMES_PAR_ONCE = 31.1035
FICHIER_ETAT = Path("etat.json")

NTFY_TOPIC = os.environ["NTFY_TOPIC"]

# Alerte quand le cours passe SOUS un de ces niveaux (EUR par gramme)
NIVEAUX_BAISSE = [114, 115, 116, 118]

# Alerte quand le cours passe AU-DESSUS d'un de ces niveaux (vide = aucune alerte à la hausse)
NIVEAUX_HAUSSE = [119,120,121]

# Délai minimum entre deux alertes sur un même niveau (évite le spam si le cours oscille)
DELAI_MIN_SECONDES = 60 * 60


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
    etat = {"dernier_prix": None, "alertes": {}}
    if FICHIER_ETAT.exists():
        etat.update(json.loads(FICHIER_ETAT.read_text()))

    prix = prix_or_gramme_eur()
    dernier = etat["dernier_prix"]
    print(f"Or : {prix:.2f} EUR/g (précédent : {dernier})")

    lignes = []
    maintenant = time.time()

    if dernier is not None:
        for niveau in sorted(NIVEAUX_BAISSE, reverse=True):
            cle = f"baisse_{niveau}"
            if maintenant - etat["alertes"].get(cle, 0) < DELAI_MIN_SECONDES:
                continue
            if dernier > niveau >= prix:
                lignes.append(f"⬇️ Passé sous {niveau} EUR/g")
                etat["alertes"][cle] = maintenant

        for niveau in sorted(NIVEAUX_HAUSSE):
            cle = f"hausse_{niveau}"
            if maintenant - etat["alertes"].get(cle, 0) < DELAI_MIN_SECONDES:
                continue
            if dernier < niveau <= prix:
                lignes.append(f"⬆️ Passé au-dessus de {niveau} EUR/g")
                etat["alertes"][cle] = maintenant

    if lignes:
        notifier("Or : niveau franchi", "\n".join(lignes) + f"\nCours actuel : {prix:.2f} EUR/g")

    etat["dernier_prix"] = prix
    FICHIER_ETAT.write_text(json.dumps(etat))


if __name__ == "__main__":
    main()
