import os
import logging
from azure.cosmos import CosmosClient, PartitionKey

# Singleton: il container client viene creato una sola volta e riusato per tutta la vita del worker.
_container_client = None


def get_container():
    """
    Crea (se non esiste) e restituisce il container client di Cosmos DB.
    Usa un singleton per evitare di ricreare la connessione ad ogni invocazione.
    """
    global _container_client
    if _container_client is not None:
        return _container_client

    cosmos_connection = os.environ["COSMOS_CONNECTION"]
    database_name = os.environ["COSMOS_DB_NAME"]
    container_name = os.environ["COSMOS_CONTAINER_NAME"]

    client = CosmosClient.from_connection_string(cosmos_connection)
    database = client.get_database_client(database_name)

    # Crea il container se non esiste, con TTL abilitato (default: i documenti non scadono)
    _container_client = database.create_container_if_not_exists(
        id=container_name,
        partition_key=PartitionKey(path="/id"),
        default_ttl=-1
    )
    return _container_client


def save_document(document: dict):
    """
    Salva un documento JSON nel container Cosmos DB.
    """
    container = get_container()
    return container.create_item(body=document)


def delete_document(comic_id: str):
    """
    Elimina un documento da Cosmos DB dato il suo ID.
    """
    try:
        container = get_container()
        container.delete_item(item=comic_id, partition_key=comic_id)
        logging.info(f"Fumetto {comic_id} eliminato da Cosmos DB.")
    except Exception as e:
        logging.warning(f"Fumetto non trovato in Cosmos DB o già eliminato: {str(e)}")
