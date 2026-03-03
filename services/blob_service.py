import os
import logging
from urllib.parse import urlparse
from azure.storage.blob import BlobServiceClient
from azure.core.exceptions import ResourceNotFoundError
from azure.identity import DefaultAzureCredential

def delete_blob(blob_url: str):
    """
    Elimina un blob dato il suo URL.
    """

    parsed_url = urlparse(blob_url)
    path_parts = parsed_url.path.lstrip('/').split('/', 1)

    if len(path_parts) < 2:
        logging.warning(f"URL blob non valido, impossibile eliminare: {blob_url}")
        return

    container_name = path_parts[0]
    blob_name = path_parts[1]

    try:
        credential = DefaultAzureCredential()
        blob_service_client = BlobServiceClient(account_url=os.environ["STORAGE_ENDPOINT"], credential=credential)
        blob_client = blob_service_client.get_blob_client(container=container_name, blob=blob_name)
        blob_client.delete_blob()
        logging.info(f"Blob eliminato: {blob_name}")
    except ResourceNotFoundError:
        # Il blob non esiste già
        logging.warning(f"Blob già eliminato o non trovato (ignorato): {blob_name}")
    except Exception as e:
        logging.error(f"Errore eliminazione blob '{blob_name}': {e}")
        raise


def extract_user_id(blob_url: str) -> str:
    """Estrae lo user_id dal percorso del blob URL (penultimo segmento del path)."""
    path_parts = urlparse(blob_url).path.split('/')
    return path_parts[-2] if len(path_parts) >= 2 else "unknown"
