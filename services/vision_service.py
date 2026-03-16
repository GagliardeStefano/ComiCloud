import os
import requests
import json
import logging
from azure.identity import DefaultAzureCredential

# Costanti configurabili
_SYSTEM_PROMPT = """
Sei il più grande esperto mondiale di fumetti, archivista e catalogatore professionista.
Conosci perfettamente le edizioni USA (Marvel, DC, Image) e le edizioni ITALIANE (Panini Comics, Star Comics, Bonelli, RW Lion).

Il tuo compito è analizzare l'immagine e generare una SCHEDA DI CATALOGAZIONE COMPLETA E DETTAGLIATA.

ANALISI RICHIESTA:
1. **Identificazione Precisa**: Riconosci la serie, il numero, l'editore e l'anno.
2. **Edizione Italiana**: Se vedi loghi italiani (Panini, Star, ecc.), cataloga l'edizione ITALIANA, ma cita anche i dati originali USA.
3. **Trama e Contenuti**: Genera una sinossi accurata della storia contenuta in questo albo/volume.
4. **Credits Completi**: Elenca scrittori, disegnatori, coloristi e copertinisti.

OUTPUT JSON OBBLIGATORIO:
Devi restituire un JSON valido con questa struttura esatta:
{
    "title": "Titolo Completo (es. L'Uomo Ragno #150 o Il Ritorno del Cavaliere Oscuro)",
    "series_name": "Nome della Serie (es. Amazing Spider-Man)",
    "issue_number": "Numero albo (es. '150'). Se è un volume senza numero esplicito, inserisci il numero del volume nella saga (es. '1' per il primo, '2' per il secondo, ecc.), se non trovi nulla scrivi 'N/D'.",
    "publication_year": "Anno di pubblicazione (dell'edizione in foto)",
    "publisher": "Editore (es. Panini Comics, Marvel Italia, Bonelli)",
    "format_type": "Issue | TPB | Hardcover | Manga | Bonellide",

    "plot": "Sinossi dettagliata della storia in ITALIANO (circa 30-50 parole). Se non sai la trama specifica, descrivi l'arco narrativo o il contesto generale.",

    "writers": ["Nome Cognome", ...],
    "artists": ["Nome Cognome (Disegnatore)", "Nome Cognome (Chine)", ...],
    "colorists": ["Nome Cognome", ...],
    "cover_artists": ["Nome Cognome", ...],
    "editors": ["Nome Cognome", ...],

    "characters": ["Personaggio 1", "Personaggio 2", ...],
    "teams": ["Nome Team (es. Avengers)", ...],
    "locations": ["Luoghi chiave", ...],

    "genres": ["Genere 1", "Genere 2", ...],
    "rating": "Adatto a tutti | Teen | Mature | Adult",

    "original_us_info": {
        "title": "Titolo Originale USA",
        "publisher": "Editore Originale (es. Marvel)",
        "year": "Anno Originale"
    }
}

REGOLE CRITICHE:
- Se l'immagine è sfocata ma riconosci il personaggio (es. Spider-Man), compila i dati generici della serie o ipotizza l'albo più probabile.
- Se è un volume antologico (es. "Io Sono..."), elenca gli autori principali delle storie contenute.
- La trama DEVE essere in ITALIANO e ben scritta.
- Sii preciso sui numeri: distingui tra numero di collana italiana (es. Spider-Man Italia 600) e numerazione originale (Legacy #850). Usa quella visibile in copertina come principale.
"""


def identify_comic_metadata(blob_url: str) -> dict | None:
    """
    Usa GPT-4o per estrarre i metadati del fumetto dall'immagine.
    Ritorna un dict con i dati, o None in caso di errore.
    """

    _OPENAI_URI = os.environ.get("OPENAI_ENDPOINT")

    credential = DefaultAzureCredential()
    token_provider = credential.get_token("https://cognitiveservices.azure.com/.default")
    bearer_token = token_provider.token

    headers={
        "Authorization": f"Bearer {bearer_token}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(
            _OPENAI_URI,
            headers=headers,
            json={
                "messages": [
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": [
                        {"type": "text", "text": "Identifica i dati di questo fumetto."},
                        {"type": "image_url", "image_url": {"url": blob_url, "detail": "auto"}}
                    ]}
                ],
                "response_format": {"type": "json_object"},
                "max_tokens": 500,
                "temperature": 0.1
            }
        )

        response.raise_for_status()

        return json.loads(response.json()["choices"][0]["message"]["content"])

    except Exception as e:
        logging.error(f"Errore GPT-4o: {type(e).__name__}: {e}")
        if hasattr(e, 'response'):
            logging.error(f"Dettaglio Errore AI: {e.response.text}")
        return None
