import os
import uuid
from flask import Flask, render_template, request, jsonify, redirect
from azure.storage.blob import BlobServiceClient
from azure.cosmos import CosmosClient
from werkzeug.middleware.proxy_fix import ProxyFix
from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential
import filetype
import logging
import sys
from azure.servicebus import ServiceBusClient, ServiceBusMessage
import json

# Configurazione logging per Flask (visibile in Azure Log Stream)
logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

app.config['PREFERRED_URL_SCHEME'] = 'https'
app.config['SESSION_COOKIE_SECURE'] = True

app.wsgi_app = ProxyFix(
    app.wsgi_app,
    x_for=1,
    x_proto=1,
    x_host=1,
    x_prefix=1
)

# Configurazione Azure (variabili d'ambiente)
STORAGE_CONNECTION = os.environ.get("STORAGE_CONNECTION")
COSMOS_CONNECTION = os.environ.get("COSMOS_CONNECTION")
SERVICEBUS_CONNECTION = os.environ.get("SERVICEBUS_CONNECTION")
SERVICEBUS_NAME = os.environ.get("SERVICEBUS_NAME")

COSMOS_DB_NAME = os.environ["COSMOS_DB_NAME"]
COSMOS_CONTAINER_NAME = os.environ["COSMOS_CONTAINER_NAME"]
BLOB_CONTAINER_NAME = os.environ["BLOB_CONTAINER_NAME"]

SEARCH_ENDPOINT = os.environ.get("SEARCH_ENDPOINT")
SEARCH_INDEX_NAME = os.environ.get("SEARCH_INDEX_NAME")
SEARCH_KEY = os.environ.get("SEARCH_KEY")

@app.after_request
def add_security_headers(response):
    """Aggiunge header di sicurezza alla risposta"""
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; img-src 'self' data: https:;"
    return response

def get_user_id():
    """
    Recupera l'ID utente da Entra ID Easy Auth.
    In produzione, Azure passa l'header X-MS-CLIENT-PRINCIPAL-ID.
    """
    user_id = request.headers.get('X-MS-CLIENT-PRINCIPAL-ID')
    if not user_id:
        # Fallback per testing locale
        user_id = "test-user-local"
    return user_id

def get_user_email():
    """Recupera email utente da Easy Auth"""
    email = request.headers.get('X-MS-CLIENT-PRINCIPAL-NAME')
    return email or "user@example.com"

@app.route('/')
def home():
    """Pagina principale: upload foto"""
    user_email = get_user_email()
    return render_template('home.html', user_email=user_email)

@app.route('/collezione')
def collezione():
    """Pagina collezione: mostra i fumetti dell'utente"""
    user_id = get_user_id()
    user_email = get_user_email()

    comics = []
    try:
        client = CosmosClient.from_connection_string(COSMOS_CONNECTION)
        database = client.get_database_client(COSMOS_DB_NAME)
        container = database.get_container_client(COSMOS_CONTAINER_NAME)

        query = "SELECT * FROM c WHERE (c.user_id = @user_id OR NOT IS_DEFINED(c.user_id)) AND c.status != 'error'"
        parameters = [{"name": "@user_id", "value": user_id}]

        items = container.query_items(
            query=query,
            parameters=parameters,
            enable_cross_partition_query=True
        )

        comics = list(items)
    except Exception as e:
        print(f"Errore query Cosmos: {e}")

    return render_template('collezione.html', comics=comics, user_email=user_email)


@app.route('/logout')
def logout():
    return redirect("/.auth/logout?post_logout_redirect_uri=/")

@app.route('/api/upload', methods=['POST'])
def upload_image():
    """API per caricare immagini su Blob Storage"""
    if 'file' not in request.files:
        return jsonify({'error': 'Nessun file'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'Nome file vuoto'}), 400

    # Validazione dimensione file (MAX 5MB)
    MAX_FILE_SIZE = 5 * 1024 * 1024
    file.seek(0, os.SEEK_END)
    file_length = file.tell()
    file.seek(0)

    if file_length > MAX_FILE_SIZE:
        return jsonify({'error': 'Il file è troppo grande (Max 5MB)'}), 413

    # Validazione tipo di file (Magic Bytes)
    header = file.read(2048)
    file.seek(0)

    kind = filetype.guess(header)
    if kind is None or not kind.mime.startswith('image/'):
        return jsonify({'error': 'Il file non è un\'immagine valida'}), 400

    try:
        user_id = get_user_id()

        file_extension = kind.extension
        blob_name = f"{user_id}/{uuid.uuid4()}.{file_extension}"

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
        return jsonify({'error': str(e)}), 500

@app.route('/api/comic/<comic_id>')
def get_comic_details(comic_id):
    """API per ottenere dettagli di un fumetto specifico"""
    try:
        client = CosmosClient.from_connection_string(COSMOS_CONNECTION)
        database = client.get_database_client(COSMOS_DB_NAME)
        container = database.get_container_client(COSMOS_CONTAINER_NAME)

        comic = container.read_item(item=comic_id, partition_key=comic_id)
        return jsonify(comic)
    except Exception as e:
        return jsonify({'error': str(e)}), 404

def delete_comic_from_search(comic_id):
    if not SEARCH_ENDPOINT or not SEARCH_KEY:
        print("Search ignorato (Mancano SEARCH_ENDPOINT o SEARCH_KEY)")
        return
    try:
        search_client = SearchClient(
            endpoint=SEARCH_ENDPOINT,
            index_name=SEARCH_INDEX_NAME,
            credential=AzureKeyCredential(SEARCH_KEY)
        )
        documents_to_delete = [{"id": comic_id}]
        result = search_client.delete_documents(documents=documents_to_delete)
        print(f"Eliminazione da Search riuscita: {result[0].succeeded}")
    except Exception as e:
        print(f"Errore durante l'eliminazione da Search: {e}")

@app.route('/api/delete_comic/<comic_id>', methods=['DELETE'])
def delete_comic(comic_id):
    """Elimina un fumetto dal database"""
    try:
        user_id = get_user_id()
        client = CosmosClient.from_connection_string(COSMOS_CONNECTION)
        database = client.get_database_client(COSMOS_DB_NAME)
        container = database.get_container_client(COSMOS_CONTAINER_NAME)

        # 1. Recupera il documento per verificare la proprietà (IDOR Fix)
        try:
            item = container.read_item(item=comic_id, partition_key=comic_id)
        except Exception:
            return jsonify({'error': 'Fumetto non trovato'}), 404

        # 2. Verifica che l'utente sia il proprietario
        if item.get('user_id') and item.get('user_id') != user_id:
            return jsonify({'error': 'Non autorizzato a eliminare questo fumetto'}), 403

        # 3. Elimina il documento
        container.delete_item(item=comic_id, partition_key=comic_id)

        delete_comic_from_search(comic_id)

        return jsonify({'success': True, 'message': 'Fumetto eliminato'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/check_status')
def check_status():
    """Controlla se l'analisi AI è completata cercando il documento su Cosmos DB"""
    user_id = get_user_id()
    blob_name = request.args.get('blob_name')

    if not blob_name:
        return jsonify({'status': 'error', 'message': 'Manca blob_name'}), 400

    try:
        client = CosmosClient.from_connection_string(COSMOS_CONNECTION)
        database = client.get_database_client(COSMOS_DB_NAME)
        container = database.get_container_client(COSMOS_CONTAINER_NAME)

        query = "SELECT * FROM c WHERE c.user_id = @user_id AND CONTAINS(c.original_image_url, @blob_name)"
        parameters = [
            {"name": "@user_id", "value": user_id},
            {"name": "@blob_name", "value": blob_name}
        ]

        print(f"DEBUG: check_status polling for user={user_id}, blob={blob_name}")
        items = list(container.query_items(
            query=query,
            parameters=parameters,
            enable_cross_partition_query=True
        ))
        print(f"DEBUG: Found {len(items)} items")

        if len(items) > 0:
            doc = items[0]
            if doc.get('status') == 'error':
                return jsonify({
                    'status': 'error',
                    'message': 'Non siamo riusciti a identificare il fumetto.',
                    'comic': doc
                })
            return jsonify({'status': 'completed', 'comic': doc})
        else:
            return jsonify({'status': 'pending'})

    except Exception as e:
        return jsonify({'status': 'error', 'details': str(e)}), 500

@app.route('/api/search')
def search_comics():
    """API che interroga Azure AI Search"""
    user_id = get_user_id()
    query = request.args.get('q', '*')

    if not SEARCH_ENDPOINT or not SEARCH_KEY:
        print("ERRORE CRITICO: Variabili SEARCH_ENDPOINT o SEARCH_KEY mancanti!")
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

        output = []
        for res in results:
            output.append({
                'id': res['id'],
                'metadata': res['metadata']
            })

        return jsonify({'results': output})

    except Exception as e:
        print(f"Errore Search: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8000)