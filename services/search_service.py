import os
import logging


def _get_search_client():
    """
    Crea e restituisce un'istanza di SearchClient (lazy import per evitare crash al startup).
    """
    # Import lazy: se il modulo manca, il crash avviene solo quando si usa Search,
    # non al caricamento del worker (che impedirebbe la registrazione di TUTTE le function).
    from azure.search.documents import SearchClient
    from azure.core.credentials import AzureKeyCredential

    endpoint = os.environ.get("SEARCH_ENDPOINT")
    key = os.environ.get("SEARCH_KEY")
    index_name = os.environ.get("SEARCH_INDEX_NAME")

    if not endpoint or not key or not index_name:
        raise ValueError("Variabili SEARCH_ENDPOINT, SEARCH_KEY o SEARCH_INDEX_NAME mancanti.")

    return SearchClient(
        endpoint=endpoint,
        index_name=index_name,
        credential=AzureKeyCredential(key)
    )


def upload_to_search(document: dict):
    """
    Carica o aggiorna un documento nell'indice di AI Search.
    """
    try:
        client = _get_search_client()
        client.upload_documents([document])
        logging.info(f"Documento {document.get('id')} caricato su AI Search.")
    except Exception as e:
        logging.error(f"Errore upload su AI Search: {str(e)}")
        raise


def delete_from_search(comic_id: str):
    """
    Elimina un documento dall'indice di AI Search dato il suo ID.
    """
    try:
        client = _get_search_client()
        client.delete_documents([{"id": comic_id}])
        logging.info(f"Documento {comic_id} eliminato da AI Search.")
    except Exception as e:
        logging.warning(f"Errore eliminazione da AI Search (ignorato): {str(e)}")
