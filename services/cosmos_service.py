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
    database = client.get_database_client(database_name)
        
    try:
        container = database.get_container_client(container_name)
        # Leggiamo le proprietà attuali
        properties = container.read()
        if 'defaultTtl' not in properties:
           # -1 significa "i documenti non scadono"
            properties['defaultTtl'] = -1 
            database.replace_container(container_name, partition_key=properties['partitionKey'], default_ttl=-1)
    except Exception:
        from azure.cosmos import PartitionKey
        container = database.create_container_if_not_exists(
            id=container_name,
            partition_key=PartitionKey(path="/id"),
            default_ttl=-1
        )
    
    return container.create_item(body=document)
