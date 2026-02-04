import os
from datetime import datetime, timedelta
from azure.storage.blob import generate_blob_sas, BlobSasPermissions
from urllib.parse import urlparse

def generate_sas_url(blob_url: str) -> str:
    """
    Genera un URL con SAS token per l'accesso in lettura a un blob privato.
    """
    storage_connection_string = os.environ["STORAGE_CONNECTION"]
    
    # Parsing URL per estrarre container e blob name
    parsed_url = urlparse(blob_url)
    path_parts = parsed_url.path.lstrip('/').split('/', 1)
    
    if len(path_parts) < 2:
        raise ValueError(f"URL Blob non valido: {blob_url}")
        
    container_name = path_parts[0]
    blob_name = path_parts[1]
    account_name = parsed_url.netloc.split('.')[0]

    # Estrazione Account Key
    storage_key = None
    for part in storage_connection_string.split(';'):
        if part.startswith('AccountKey='):
            storage_key = part.split('=', 1)[1]
            break
            
    if not storage_key:
        raise ValueError("Impossibile trovare AccountKey in STORAGE_CONNECTION")

    # Generazione Token
    sas_token = generate_blob_sas(
        account_name=account_name,
        container_name=container_name,
        blob_name=blob_name,
        account_key=storage_key,
        permission=BlobSasPermissions(read=True),
        expiry=datetime.utcnow() + timedelta(minutes=15)
    )

    return f"{blob_url}?{sas_token}"
