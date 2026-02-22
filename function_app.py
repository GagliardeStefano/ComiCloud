import azure.functions as func
import logging
import json
import uuid
import os
from datetime import datetime
from services.blob_service import delete_blob
from services.vision_service import identify_comic_metadata
from services.cosmos_service import save_document
from urllib.parse import urlparse
from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential
from azure.cosmos import CosmosClient

app = func.FunctionApp()

# parte quando arriva un messaggio sulla coda
@app.service_bus_queue_trigger(arg_name="msg", 
                               queue_name="process-image-queue", 
                               connection="SERVICEBUS_CONNECTION") 

def process_comic(msg: func.ServiceBusMessage):

    logging.info(f"Trigger elaborazione fumetto avviato per: {msg.get_body().decode('utf-8')}")

    try:
        # 1. Parsing del messaggio
        message_body = msg.get_body().decode('utf-8')
        logging.info(f"DEBUG: Body del messaggio: {message_body}")
        event_data = json.loads(message_body)

        if isinstance(event_data, list):
            event_data = event_data[0]

        # estrazione URL del blob
        blob_url = event_data['data']['url']

        target_container = os.environ["BLOB_CONTAINER_NAME"]
        if f"/{target_container.lower()}/" not in blob_url.lower():
            logging.warning(f"Il file non si trova nel container '{target_container}'. URL: {blob_url}")
            return
        valid_extensions = (".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff")
        if not blob_url.lower().endswith(valid_extensions):
            logging.warning(f"Il file non è un'immagine supportata. URL: {blob_url}")
            return
        logging.info(f"Processando immagine: {blob_url}")
  
        # 3. Analisi AI (GPT-4o)
        logging.info("Chiedo a GPT-4o di identificare e catalogare il fumetto...")
        ai_data = identify_comic_metadata(blob_url)
        
        comic_metadata = None

        if ai_data:
            logging.info(f"AI ha restituito dati: {ai_data.get('title')}")

            # mapping diretto dai dati AI al formato interno DB
            comic_metadata = {
                "title": ai_data.get('title', 'Titolo Sconosciuto'),
                "issue_number": ai_data.get('issue_number'),
                "publish_date": ai_data.get('publication_year', 'N/D'),
                "plot": ai_data.get('plot', 'Trama non disponibile.'),
                "cover_url": blob_url, # foto scattata dall'utente
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
            # NESSUN METADATA: errore.
            comic_metadata = None

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
            "status": "processed" if comic_metadata else "error", 
            "upload_timestamp": datetime.utcnow().isoformat()+"Z",
            "metadata": comic_metadata
        }
        
        # TTL (60 secondi) per cancellare fumetto non identificato se il frontend fallisce
        if not comic_metadata:
            comic_document['ttl'] = 60
            logging.info(f"Eliminazione blob associato all'errore: {blob_url}")
            delete_blob(blob_url)

        # 6. Salvataggio su Cosmos DB
        save_document(comic_document)
        logging.info(f"Documento {doc_id} salvato su Cosmos DB!")

        # 7. Aggiornamento su Ai Search
        if comic_metadata:
            try:
                # Nota: Ricordati di usare SearchClient
                search_client = SearchClient(
                    endpoint=os.environ["SEARCH_ENDPOINT"],
                    index_name=os.environ["SEARCH_INDEX_NAME"],
                    credential=AzureKeyCredential(os.environ["SEARCH_KEY"])
                )
                
                # Invia l'intero documento sistemato
                search_client.upload_documents([comic_document])
                logging.info(f"Fumetto {doc_id} caricato istantaneamente su AI Search!")
            except Exception as e:
                logging.error(f"Errore durante l'upload su AI Search: {str(e)}")
    except Exception as e:
        logging.error(f"Errore critico durante l'elaborazione del messaggio: {str(e)}")
        # rilanciare l'eccezione per far riprovare al Service Bus   
        raise e


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

        # 2. ELIMINAZIONE BLOB
        if blob_url:
            try:
                delete_blob(blob_url) 
                logging.info(f"Blob eliminato con successo: {blob_url}")
            except Exception as e:
                logging.warning(f"Impossibile eliminare il blob o già eliminato: {str(e)}")

        # 3. ELIMINAZIONE DA COSMOS DB
        try:
            cosmos_connection = os.environ["COSMOS_CONNECTION"]
            client = CosmosClient.from_connection_string(cosmos_connection)
            database = client.get_database_client(os.environ["COSMOS_DB_NAME"])
            container = database.get_container_client(os.environ["COSMOS_CONTAINER_NAME"])
            
            container.delete_item(item=comic_id, partition_key=comic_id)
            logging.info(f"Fumetto {comic_id} eliminato da Cosmos DB.")
        except Exception as e:
            logging.warning(f"Fumetto non trovato in Cosmos DB o già eliminato: {str(e)}")

        # 4. ELIMINAZIONE DA AI SEARCH
        search_endpoint = os.environ.get("SEARCH_ENDPOINT")
        search_key = os.environ.get("SEARCH_KEY")
        search_index = os.environ.get("SEARCH_INDEX_NAME")

        if search_endpoint and search_key:
            try:
                search_client = SearchClient(
                    endpoint=search_endpoint,
                    index_name=search_index,
                    credential=AzureKeyCredential(search_key)
                )
                search_client.delete_documents([{"id": comic_id}])
                logging.info(f"Fumetto {comic_id} eliminato da AI Search.")
            except Exception as e:
                logging.warning(f"Errore durante l'eliminazione da AI Search: {str(e)}")
        else:
            logging.error("Variabili di ambiente per AI Search mancanti nella Function App.")

    except Exception as e:
        logging.error(f"Errore critico durante l'eliminazione: {str(e)}")
        # Solleviamo l'eccezione in modo che il Service Bus riprovi l'esecuzione (Retry Policy)
        raise e