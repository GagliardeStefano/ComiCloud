import azure.functions as func
import logging
import json
import uuid
import os
from datetime import datetime
from services.blob_service import delete_blob, extract_user_id
from services.vision_service import identify_comic_metadata
from services.cosmos_service import save_document, delete_document
from services.search_service import upload_to_search, delete_from_search

app = func.FunctionApp()

# Trigger: elabora una nuova immagine ricevuta dalla coda
@app.service_bus_queue_trigger(arg_name="msg",
                               queue_name="process-image-queue",
                               connection="SERVICEBUS_CONNECTION")
def process_comic(msg: func.ServiceBusMessage):

    logging.info(f"Trigger elaborazione fumetto avviato per: {msg.get_body().decode('utf-8')}")

    try:
        # 1. Parsing del messaggio
        message_body = msg.get_body().decode('utf-8')
        logging.info(f"Body del messaggio: {message_body}")
        event_data = json.loads(message_body)

        if isinstance(event_data, list):
            event_data = event_data[0]

        # 2. Estrazione URL del blob
        data_payload = event_data.get('data', {})
        blob_url = data_payload.get('url')

        if not blob_url:
            logging.error("Payload non valido o URL mancante. Messaggio scartato.")
            return

        target_container = os.environ["BLOB_CONTAINER_NAME"]
        valid_extensions = (".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff")

        if f"/{target_container.lower()}/" not in blob_url.lower() or not blob_url.lower().endswith(valid_extensions):
            logging.warning(f"File scartato (container errato o estensione non valida). URL: {blob_url}")
            user_id = extract_user_id(blob_url)
            error_doc = {
                "id": str(uuid.uuid4()),
                "user_id": user_id,
                "original_image_url": blob_url,
                "status": "error",
                "ttl": 60
            }
            save_document(error_doc)
            delete_blob(blob_url)
            return

        logging.info(f"Processando immagine: {blob_url}")

        # 3. Analisi AI (GPT-4o)
        logging.info("Chiedo a GPT-4o di identificare e catalogare il fumetto...")
        ai_data = identify_comic_metadata(blob_url)

        comic_metadata = None
        if ai_data:
            logging.info(f"AI ha restituito dati: {ai_data.get('title')}")
            comic_metadata = {
                "title": ai_data.get('title', 'Titolo Sconosciuto'),
                "issue_number": ai_data.get('issue_number'),
                "publish_date": ai_data.get('publication_year', 'N/D'),
                "plot": ai_data.get('plot', 'Trama non disponibile.'),
                "cover_url": blob_url,
                "publisher": ai_data.get('publisher', 'N/D'),
                "format_type": ai_data.get('format_type', 'Issue'),
                
                # credits
                "writers": ai_data.get('writers', ['N/D']),
                "artists": ai_data.get('artists', ['N/D']),
                "colorists": ai_data.get('colorists', ['N/D']),
                "letterers": ai_data.get('letterers', ['N/D']),
                "editors": ai_data.get('editors', ['N/D']),
                "cover_artists": ai_data.get('cover_artists', ['N/D']),
                
                # content
                "characters": ai_data.get('characters', ['N/D']),
                "teams": ai_data.get('teams', ['N/D']),
                "locations": ai_data.get('locations', ['N/D']),
                "genres": ai_data.get('genres', ['N/D']),
                "rating": ai_data.get('rating', 'N/D'),
                
                "original_us_info": ai_data.get('original_us_info', {}),
                "ai_is_pure_source": True
            }
        else:
            logging.error("GPT-4o non è riuscito ad analizzare l'immagine.")

        # 4. Estrazione user_id e creazione documento
        doc_id = str(uuid.uuid4())
        user_id = extract_user_id(blob_url)

        comic_document = {
            "id": doc_id,
            "user_id": user_id,
            "original_image_url": blob_url,
            "ai_analysis": ai_data,
            "status": "processed" if comic_metadata else "error",
            "upload_timestamp": datetime.utcnow().isoformat() + "Z",
            "metadata": comic_metadata
        }

        # TTL breve per auto-eliminare fumetti non identificati se il frontend fallisce
        if not comic_metadata:
            comic_document['ttl'] = 60

        # 5. Salvataggio su Cosmos DB (SEMPRE prima di eliminare file fisici)
        save_document(comic_document)
        logging.info(f"Documento {doc_id} salvato su Cosmos DB.")

        if not comic_metadata:
            logging.info(f"Eliminazione blob associato all'errore: {blob_url}")
            delete_blob(blob_url)
            return

        # 6. Indicizzazione su AI Search
        upload_to_search(comic_document)

    except Exception as e:
        logging.error(f"Errore critico durante l'elaborazione del messaggio: {str(e)}")
        raise


# Trigger: elimina un fumetto su richiesta del frontend
@app.service_bus_queue_trigger(arg_name="msg",
                               queue_name="delete-comic-queue",
                               connection="SERVICEBUS_CONNECTION")
def process_delete_comic(msg: func.ServiceBusMessage):

    logging.info("Trigger eliminazione fumetto avviato.")

    try:
        # 1. Parsing del messaggio
        event_data = json.loads(msg.get_body().decode('utf-8'))
        comic_id = event_data.get('comic_id')
        blob_url = event_data.get('blob_url')

        if not comic_id:
            logging.error("ID Fumetto mancante nel messaggio di eliminazione.")
            return

        # 2. Eliminazione Blob
        if blob_url:
            try:
                delete_blob(blob_url)
                logging.info(f"Blob eliminato con successo: {blob_url}")
            except Exception as e:
                logging.warning(f"Impossibile eliminare il blob o già eliminato: {str(e)}")

        # 3. Eliminazione da Cosmos DB
        delete_document(comic_id)

        # 4. Eliminazione da AI Search
        delete_from_search(comic_id)

    except Exception as e:
        logging.error(f"Errore critico durante l'eliminazione: {str(e)}")
        raise

