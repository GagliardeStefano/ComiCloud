import azure.functions as func
import logging
import json
import uuid
from datetime import datetime
from services.blob_service import generate_sas_url
from services.vision_service import identify_comic_metadata
from services.cosmos_service import save_document
from urllib.parse import urlparse

app = func.FunctionApp()

# parte quando arriva un messaggio sulla coda
@app.service_bus_queue_trigger(arg_name="msg", 
                               queue_name="process-image-queue", 
                               connection="SERVICEBUS_CONNECTION") 

def process_comic(msg: func.ServiceBusMessage):

    logging.info('Trigger elaborazione fumetto avviato')

    try:
        # 1. Parsing del messaggio
        message_body = msg.get_body().decode('utf-8')
        event_data = json.loads(message_body)

        if isinstance(event_data, list):
            event_data = event_data[0]

        # estrazione URL del blob
        blob_url = event_data['data']['url']
        logging.info(f"Processando immagine: {blob_url}")

        # 2. Generazione SAS URL (Blob Service)
        sas_url = generate_sas_url(blob_url)
        logging.info("SAS URL generato correttamente")
        
        # 3. Analisi AI (GPT-4o)
        logging.info("Chiedo a GPT-4o di identificare e catalogare il fumetto...")
        ai_data = identify_comic_metadata(sas_url)
        
        comic_metadata = None

        if ai_data:
            logging.info(f"AI ha restituito dati: {ai_data.get('title')}")

            # mapping diretto dai dati AI al formato interno DB
            comic_metadata = {
                "title": ai_data.get('title', 'Titolo Sconosciuto'),
                "issue_number": ai_data.get('issue_number', '1'),
                "publish_date": ai_data.get('publication_year'),
                "store_date": None,
                "plot": ai_data.get('plot', 'Trama non disponibile.'),
                "cover_url": sas_url, # foto scattata dall'utente
                "comic_vine_url": None,
                "publisher": ai_data.get('publisher', 'N/D'),
                "format_type": ai_data.get('format_type', 'Issue'),
                
                # credits
                "writers": ai_data.get('writers', []),
                "artists": ai_data.get('artists', []),
                "colorists": ai_data.get('colorists', []),
                "letterers": ai_data.get('letterers', []),
                "editors": ai_data.get('editors', []),
                "cover_artists": ai_data.get('cover_artists', []),
                
                # content
                "characters": ai_data.get('characters', []),
                "teams": ai_data.get('teams', []),
                "locations": ai_data.get('locations', []),
                "genres": ai_data.get('genres', []),
                "rating": ai_data.get('rating'),
                
                "original_us_info": ai_data.get('original_us_info', {}),
                "ai_is_pure_source": True
            }
        else:
            logging.error("GPT-4o non è riuscito ad analizzare l'immagine.")
            # fallback 
            comic_metadata = {
                "title": "NON IDENTIFICATO",
                "plot": "Impossibile identificare il fumetto. Riprova a scattare una foto più chiara.",
                "cover_url": sas_url
            }

        # 5. Creazione documento JSON
        doc_id = str(uuid.uuid4())
        
        # estrazione user_id dal percorso blob
        parsed = urlparse(blob_url)
        path_parts = parsed.path.split('/')
        user_id = path_parts[-2] if len(path_parts) >= 2 else "unknown"

        comic_document = {
            "id": doc_id,
            "user_id": user_id, 
            "original_image_url": blob_url, 
            "ai_analysis": ai_data,
            "status": "processed",
            "upload_timestamp": datetime.utcnow().isoformat(),
            "metadata": comic_metadata
        }

        # 6. Salvataggio su Cosmos DB
        save_document(comic_document)
        logging.info(f"Documento {doc_id} salvato su Cosmos DB!")

    except Exception as e:
        logging.error(f"Errore critico durante l'elaborazione del messaggio: {str(e)}")
        # rilanciare l'eccezione per far riprovare al Service Bus   
        raise e
