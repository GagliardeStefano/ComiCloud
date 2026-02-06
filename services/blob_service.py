import os
from urllib.parse import urlparse


def delete_blob(blob_url: str):
    """
    Elimina un blob dato il suo URL.
    """
    storage_connection_string = os.environ["STORAGE_CONNECTION"]
    
    try:
        # Parsing URL
        parsed_url = urlparse(blob_url)
        path_parts = parsed_url.path.lstrip('/').split('/', 1)
        
        if len(path_parts) < 2:
            return # URL non valido, ignoriamo
            
        container_name = path_parts[0]
        blob_name = path_parts[1]
        
        from azure.storage.blob import BlobServiceClient
        blob_service_client = BlobServiceClient.from_connection_string(storage_connection_string)
        blob_client = blob_service_client.get_blob_client(container=container_name, blob=blob_name)
        
        blob_client.delete_blob()
        print(f"Blob eliminato: {blob_name}")
        
    except Exception as e:
        print(f"Errore eliminazione blob: {e}")

