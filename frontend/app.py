import os
import uuid
import logging
import sys
import json
from flask import Flask, render_template, request, jsonify, redirect
from azure.storage.blob import BlobServiceClient
from azure.cosmos import CosmosClient, PartitionKey
from azure.servicebus import ServiceBusClient, ServiceBusMessage
from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential
from werkzeug.middleware.proxy_fix import ProxyFix
import filetype

# Configurazione logging per Flask (visibile in Azure Log Stream)
logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Flask App
app = Flask(__name__)
app.config['PREFERRED_URL_SCHEME'] = 'https'
app.config['SESSION_COOKIE_SECURE'] = True
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

# Variabili d'ambiente
STORAGE_CONNECTION = os.environ.get("STORAGE_CONNECTION")
COSMOS_CONNECTION = os.environ.get("COSMOS_CONNECTION")
SERVICEBUS_CONNECTION = os.environ.get("SERVICEBUS_CONNECTION")
COSMOS_DB_NAME = os.environ.get("COSMOS_DB_NAME", "")
COSMOS_CONTAINER_NAME = os.environ.get("COSMOS_CONTAINER_NAME", "")
BLOB_CONTAINER_NAME = os.environ.get("BLOB_CONTAINER_NAME", "")
SEARCH_ENDPOINT = os.environ.get("SEARCH_ENDPOINT")
SEARCH_INDEX_NAME = os.environ.get("SEARCH_INDEX_NAME")
SEARCH_KEY = os.environ.get("SEARCH_KEY")

_REQUIRED = {
    "STORAGE_CONNECTION": STORAGE_CONNECTION,
    "COSMOS_CONNECTION": COSMOS_CONNECTION,
    "SERVICEBUS_CONNECTION": SERVICEBUS_CONNECTION,
    "COSMOS_DB_NAME": COSMOS_DB_NAME,
    "COSMOS_CONTAINER_NAME": COSMOS_CONTAINER_NAME,
    "BLOB_CONTAINER_NAME": BLOB_CONTAINER_NAME,
}
_missing = [k for k, v in _REQUIRED.items() if not v]
if _missing:
    logger.critical(f"Variabili d'ambiente obbligatorie mancanti: {', '.join(_missing)}")


def get_container():
    """
    Crea e restituisce il container client di Cosmos DB.
    """
    client = CosmosClient.from_connection_string(os.environ["COSMOS_CONNECTION"])
    database = client.get_database_client(os.environ["COSMOS_DB_NAME"])
    return database.create_container_if_not_exists(
        id=os.environ["COSMOS_CONTAINER_NAME"],
        partition_key=PartitionKey(path="/id"),
        default_ttl=-1
    )


@app.after_request
def add_security_headers(response):
    """Aggiunge header di sicurezza HTTP alla risposta."""
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['Content-Security-Policy'] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "img-src 'self' data: blob: https://stcomicloud.blob.core.windows.net;"
    )
    return response


def get_user_id() -> str:
    """Recupera l'ID utente da Entra ID Easy Auth. Fallback a ID fisso in locale."""
    return request.headers.get('X-MS-CLIENT-PRINCIPAL-ID') or "test-user-local"


def get_user_email() -> str:
    """Recupera l'email utente da Easy Auth."""
    return request.headers.get('X-MS-CLIENT-PRINCIPAL-NAME') or "user@example.com"


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route('/')
def home():
    """Pagina principale: upload foto."""
    return render_template('home.html', user_email=get_user_email())


@app.route('/collezione')
def collezione():
    """Pagina collezione: mostra i fumetti dell'utente."""
    user_id = get_user_id()
    comics = []
    try:
        container = get_container()
        query = "SELECT * FROM c WHERE (c.user_id = @user_id OR NOT IS_DEFINED(c.user_id)) AND c.status != 'error'"
        parameters = [{"name": "@user_id", "value": user_id}]

        comics = list(container.query_items(
            query=query,
            parameters=parameters,
            enable_cross_partition_query=True
        ))
        
    except Exception as e:
        logger.error(f"Errore query Cosmos: {e}")

    return render_template('collezione.html', comics=comics, user_email=get_user_email())


@app.route('/logout')
def logout():
    return redirect("/.auth/logout?post_logout_redirect_uri=/")


@app.route('/api/upload', methods=['POST'])
def upload_image():
    """API per caricare immagine su Blob Storage."""
    if 'file' not in request.files:
        return jsonify({'error': 'Nessun file'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'Nome file vuoto'}), 400

    # Validazione dimensione (MAX 5MB)
    MAX_FILE_SIZE = 5 * 1024 * 1024
    file.seek(0, os.SEEK_END)
    file_length = file.tell()
    file.seek(0)
    if file_length > MAX_FILE_SIZE:
        return jsonify({'error': 'Il file è troppo grande (Max 5MB)'}), 413

    # Validazione tipo via Magic Bytes
    header = file.read(2048)
    file.seek(0)

    kind = filetype.guess(header)
    if kind is None or not kind.mime.startswith('image/'):
        return jsonify({'error': "Il file non è un'immagine valida"}), 400

    try:
        user_id = get_user_id()
        blob_name = f"{user_id}/{uuid.uuid4()}.{kind.extension}"

        blob_service_client = BlobServiceClient.from_connection_string(STORAGE_CONNECTION)
        blob_client = blob_service_client.get_blob_client(
            container=BLOB_CONTAINER_NAME,
            blob=blob_name
        )

        blob_client.upload_blob(file, overwrite=True)

        return jsonify({
            'success': True,
            'message': 'Immagine caricata! La elaboreremo a breve.',
            'blob_name': blob_name
        })

    except Exception as e:
        logger.error(f"Errore upload: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/comic/<comic_id>')
def get_comic_details(comic_id):
    """API per ottenere i dettagli di un fumetto specifico."""
    try:
        user_id = get_user_id()
        container = get_container()
        comic = container.read_item(item=comic_id, partition_key=comic_id)

        if comic.get('user_id') and comic.get('user_id') != user_id:
            return jsonify({'error': 'Non autorizzato a visualizzare questo fumetto'}), 403

        return jsonify(comic)
    except Exception as e:
        return jsonify({'error': str(e)}), 404


@app.route('/api/delete_comic/<comic_id>', methods=['DELETE'])
def delete_comic(comic_id):
    """Elimina un fumetto inviando un messaggio alla coda Service Bus."""
    try:
        user_id = get_user_id()
        container = get_container()

        # 1. Recupera il documento per verificare la proprietà (IDOR Fix)
        try:
            item = container.read_item(item=comic_id, partition_key=comic_id)
        except Exception:
            return jsonify({'error': 'Fumetto non trovato'}), 404

        # 2. Verifica che l'utente sia il proprietario
        if item.get('user_id') and item.get('user_id') != user_id:
            return jsonify({'error': 'Non autorizzato a eliminare questo fumetto'}), 403

        # 3. Invia messaggio alla coda di eliminazione
        delete_message = {
            "comic_id": comic_id,
            "blob_url": item.get('original_image_url')
        }
        with ServiceBusClient.from_connection_string(SERVICEBUS_CONNECTION) as sb_client:
            sender = sb_client.get_queue_sender(queue_name="delete-comic-queue")
            with sender:
                sender.send_messages(ServiceBusMessage(json.dumps(delete_message)))

        return jsonify({'success': True, 'message': 'Eliminazione in corso...'})
    except Exception as e:
        logger.error(f"Errore delete_comic: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/check_status')
def check_status():
    """Controlla se l'analisi AI è completata cercando il documento su Cosmos DB."""
    user_id = get_user_id()
    blob_name = request.args.get('blob_name')

    if not blob_name:
        return jsonify({'status': 'error', 'message': 'Manca blob_name'}), 400

    try:
        container = get_container()
        query = "SELECT * FROM c WHERE c.user_id = @user_id AND ENDSWITH(c.original_image_url, @blob_name)"
        parameters = [
            {"name": "@user_id", "value": user_id},
            {"name": "@blob_name", "value": blob_name}
        ]

        logger.info(f"check_status polling: user={user_id}, blob={blob_name}")
        items = list(container.query_items(
            query=query,
            parameters=parameters,
            enable_cross_partition_query=True
        ))

        if items:
            doc = items[0]
            if doc.get('status') == 'error':
                return jsonify({
                    'status': 'error',
                    'message': 'Non siamo riusciti a identificare il fumetto.',
                    'comic': doc
                })
            return jsonify({'status': 'completed', 'comic': doc})

        return jsonify({'status': 'pending'})

    except Exception as e:
        logger.error(f"Errore check_status: {e}")
        return jsonify({'status': 'error', 'details': str(e)}), 500


@app.route('/api/search')
def search_comics():
    """API che interroga Azure AI Search per la ricerca full-text."""
    user_id = get_user_id()
    query = request.args.get('q', '*')

    if not SEARCH_ENDPOINT or not SEARCH_KEY:
        logger.error("Variabili SEARCH_ENDPOINT o SEARCH_KEY mancanti.")
        return jsonify({'error': 'Configurazione server incompleta'}), 500

    if not query.strip():
        query = "*"

    try:
        search_client = SearchClient(
            endpoint=SEARCH_ENDPOINT,
            index_name=SEARCH_INDEX_NAME,
            credential=AzureKeyCredential(SEARCH_KEY)
        )

        results = search_client.search(
            search_text=query,
            filter=f"user_id eq '{user_id}' and status ne 'error'",
            select=["id", "metadata"],
            top=50,
            query_type="full"
        )

        output = [{'id': res['id'], 'metadata': res['metadata']} for res in results]
        return jsonify({'results': output})

    except Exception as e:
        logger.error(f"Errore ricerca AI Search: {e}")
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8000)