import os
from azure.cosmos import CosmosClient

def save_document(document: dict):
    """
    Salva un documento JSON nel container Cosmos DB.
    """
    cosmos_connection = os.environ["COSMOS_CONNECTION"]
    database_name = os.environ["COSMOS_DB_NAME"]
    container_name = os.environ["COSMOS_CONTAINER_NAME"]
    
    client = CosmosClient.from_connection_string(cosmos_connection)
    database = client.get_database_client(database_name)
    container = database.get_container_client(container_name)
    
    return container.create_item(body=document)
