import os
from azure.core.credentials import AzureKeyCredential
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchIndex, SearchField, SearchFieldDataType, SimpleField, 
    SearchableField, VectorSearch, VectorSearchProfile, HnswAlgorithmConfiguration
)
from dotenv import load_dotenv

load_dotenv()

def create_aisearch():
    endpoint = os.getenv("AZURE_SEARCH_ENDPOINT")
    key = os.getenv("AZURE_SEARCH_KEY")
    index_name = os.getenv("AZURE_SEARCH_INDEX_NAME")
    
    client = SearchIndexClient(endpoint, AzureKeyCredential(key))

    # 1. Borrar si existe
    try:
        client.delete_index(index_name)
        print(f"[*] Índice {index_name} eliminado.")
    except:
        print("[*] No se encontró el índice, procediendo a crear.")

    # 2. Definir los campos estrictamente
    fields = [
        SimpleField(name="id", type=SearchFieldDataType.String, key=True),
        SearchableField(name="content", type=SearchFieldDataType.String, analyzer_name="es.microsoft"),
        SimpleField(name="type", type=SearchFieldDataType.String, filterable=True),
        SimpleField(name="url", type=SearchFieldDataType.String, filterable=True),
        SimpleField(name="title", type=SearchFieldDataType.String, filterable=True),
        SimpleField(name="author", type=SearchFieldDataType.String, filterable=True),
        SimpleField(name="keywords", type=SearchFieldDataType.String, filterable=True),
        SimpleField(name="language", type=SearchFieldDataType.String, filterable=True),
        SimpleField(name="publisher", type=SearchFieldDataType.String, filterable=True),
        SimpleField(name="content_hash", type=SearchFieldDataType.String, filterable=True),
        SimpleField(name="timestamp", type=SearchFieldDataType.String, filterable=True),
        # Nota: El campo vectorial es necesario para que LangChain funcione
        SearchField(name="content_vector", type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
                    searchable=True, vector_search_dimensions=1536, vector_search_profile_name="my-vector-config")
    ]

    # 3. Configuración para búsqueda vectorial (requerido por LangChain)
    vector_search = VectorSearch(
        profiles=[VectorSearchProfile(name="my-vector-config", algorithm_configuration_name="my-hnsw-config")],
        algorithms=[HnswAlgorithmConfiguration(name="my-hnsw-config")]
    )

    # 4. Crear
    index = SearchIndex(name=index_name, fields=fields, vector_search=vector_search)
    client.create_or_update_index(index)
    print(f"[+] Índice {index_name} creado exitosamente con esquema estructurado.")

if __name__ == "__main__":
    create_aisearch()