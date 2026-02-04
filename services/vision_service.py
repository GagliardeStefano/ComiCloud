import os
import json
import logging
from openai import AzureOpenAI

def identify_comic_metadata(sas_url):
    """
    Usa GPT-4o per estrarre i metadati 'puliti' dall'immagine
    """
    # Variabili d'ambiente
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    key = os.getenv("AZURE_OPENAI_KEY")
    deployment_name = "gpt-4o"

    client = AzureOpenAI(
        api_key=key,
        api_version="2024-12-01-preview",
        azure_endpoint=endpoint
    )

    system_prompt = """
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
        "issue_number": "Numero albo (o '1' se volume unico)",
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

    try:
        response = client.chat.completions.create(
            model=deployment_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": [
                    {"type": "text", "text": "Identifica i dati di questo fumetto."},
                    {"type": "image_url", "image_url": {"url": sas_url, "detail": "auto"}}
                ]}
            ],
            max_tokens=500,  # metadata aggiuntivi
            temperature=0.1 # bassa temperatura per essere precisi e deterministici
        )
        
        # pulizia della risposta (a volte GPT mette ```json ... ```)
        content = response.choices[0].message.content
        content = content.replace("```json", "").replace("```", "").strip()
        
        return json.loads(content)

    except Exception as e:
        logging.error(f"Errore GPT-4o: {e}")
        return None
