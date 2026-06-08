import os
import hashlib
import json
import re
import cloudscraper
import asyncio
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from langchain_openai import AzureChatOpenAI, AzureOpenAIEmbeddings
from langchain_experimental.text_splitter import SemanticChunker
from playwright.async_api import async_playwright
from langchain_community.vectorstores import AzureSearch
from langchain_core.documents import Document
from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential
from datetime import datetime

load_dotenv()

# Inicializar Modelos de Azure
llm = AzureChatOpenAI(
    azure_deployment=os.getenv("DEPLOYMENT_NAME_LLM"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"), 
    openai_api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    openai_api_version="2024-12-01-preview",
    temperature=0
)

embeddings = AzureOpenAIEmbeddings(
    azure_deployment=os.getenv("DEPLOYMENT_NAME_EMBEDDINGS"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    openai_api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    api_version="2024-02-01"
)

vector_store = AzureSearch(
    azure_search_endpoint=os.getenv("AZURE_SEARCH_ENDPOINT"),
    azure_search_key=os.getenv("AZURE_SEARCH_KEY"),
    index_name=os.getenv("AZURE_SEARCH_INDEX_NAME"),
    embedding_function=embeddings.embed_query,
    metadata_mode="none"
)

def get_html_metadata(url: str) -> dict:
    """
    Descarga el HTML y extrae metadatos SEO básicos de forma determinista.
    """
    print(f"[*] Descargando HTML de: {url}")
    soup = None
    language = "Unknown"
    title = "Unknown"
    author = "Unknown"
    description = ""
    
    try:
        scraper = cloudscraper.create_scraper() 
        response = scraper.get(url, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
    
    except Exception as e:
        print(f"[-] Error al descargar {url}: {e}")
        soup = None

    if soup is not None:
        html_tag = soup.find('html')
        language = html_tag.get('lang', 'Unknown') if html_tag else 'Unknown'
        
        og_title = soup.find('meta', property='og:title')
        title_tag = soup.find('title')
        title = og_title['content'] if og_title else (title_tag.get_text() if title_tag else "Unknown")
        
        author_meta = soup.find('meta', attrs={'name': 'author'})
        author = author_meta['content'] if author_meta else "Unknown"
        
        desc_meta = soup.find('meta', attrs={'name': 'description'}) or soup.find('meta', property='og:description')
        description = desc_meta['content'] if desc_meta else ""

    return {
        "language": language,
        "title": title,
        "author": author,
        "description_previa": description
    }

async def extract_html_content(url: str) -> str:
    """
    Utiliza playwright para extraer el contenido
    """
    texto_final = ""
    # Intentamos renderizar la página con Playwright para obtener contenido generado por JS
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                            "AppleWebKit/537.36 (KHTML, like Gecko) "
                            "Chrome/126.0.0.0 Safari/537.36"),
                viewport={'width': 1920, 'height': 1080}
            )
            page = await context.new_page()
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)
            # Espera inteligente:
            await page.wait_for_load_state("load")
            # Forzamos scroll para disparar cargas perezosas
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(3)
            selectores_content = ['article', 'main', '#content', '.entry-content', '.post-content']
            texto_limpio = ""

            for selector in selectores_content:
                if await page.locator(selector).count() > 0:
                    texto_limpio = await page.locator(selector).inner_text()
                    break
            if not texto_limpio:
                texto_final = await page.evaluate("document.body.innerText")
            else:
                texto_final = texto_limpio
            
            # Eliminar espacios y saltos de línea extras
            texto_final = re.sub(r'\n{3,}', '\n\n', texto_final)
            texto_final = re.sub(r'[ ]{2,}', ' ', texto_final)
            texto_final = texto_final.strip()
            
            await browser.close()
    except Exception as e:
        print(f"[!] Error al renderizar con Playwright: {e}")
        texto_final = ""
        
    return texto_final

async def get_html_content_metadata(url: str) -> dict:
    metadata = get_html_metadata(url)
    content = await extract_html_content(url)
    # Mapa de errores y sus palabras clave
    error_patterns = {
        'access denied': ["access denied", "forbidden", "don't have permission", "403"],
        'page not found': ["not found", "404", "página no encontrada"],
        'captcha': ["captcha", "verificación de seguridad", "browser check"],
    }
    
    if len(content) < 50:
        metadata['error'] = error_type
    else:
        content_lower = content.lower()
        for error_type, keywords in error_patterns.items():
            if any(kw in content_lower for kw in keywords):
                metadata['error'] = error_type
                break # Encontramos el error, no necesitamos buscar más
            
    metadata['content'] = content
    metadata['url'] = url
    return metadata

def generate_hash(text: str) -> str:
    return hashlib.md5(text.encode('utf-8')).hexdigest()
    
def refine_metadata_with_llm(datos_html: dict) -> dict:
    """
    Usa el LLM solo para lo que BeautifulSoup no puede hacer:
    Sintetizar un resumen médico y extraer palabras clave.
    """
    print(f"[*] Ejecutando análisis cognitivo con  ...")
    
    prompt = f"""
    Eres un asistente médico experto. Analiza este texto y genera ÚNICAMENTE un objeto JSON válido.
    
    Ya tenemos estos datos extraídos de la web:
    - URL: {datos_html['url']}
    - Título: {datos_html['title']}
    - author: {datos_html['author']}
    - Descripción SEO: {datos_html['description_previa']}
    
    Tu tarea:
    1. Determina el "publisher" (entidad que publica). Si es una página genérica, deduce el nombre del sitio web.
    2. Genera un "summary" de máximo 100 palabras en español evaluando el texto principal.
    3. Extrae 3 "keywords" clave.
    
    Estructura JSON requerida:
    {{
        "publisher": "Nombre de la entidad",
        "summary": "Resumen generado...",
        "keywords": ["kw1", "kw2"]
    }}
    
    Texto Principal: {datos_html['content'][:4000]}
    """
    
    response = llm.invoke(prompt)
    clean_json_str = response.content.replace("```json", "").replace("```", "").strip()
    llm_data = json.loads(clean_json_str)
    
    # Fusionamos los datos deterministas (SEO) con los generados por el LLM
    final_metadata = {**datos_html, **llm_data}
    final_metadata.pop("content")
    return final_metadata

def send_2_aisearch(content, metadata):
    # 1. Inicializar cliente nativo
    client = SearchClient(
        endpoint=os.getenv("AZURE_SEARCH_ENDPOINT"),
        index_name=os.getenv("AZURE_SEARCH_INDEX_NAME"),
        credential=AzureKeyCredential(os.getenv("AZURE_SEARCH_KEY"))
    )

    # --- SUBIDA DEL SUMMARY ---
    summary_vector = embeddings.embed_query(metadata["summary"])
    summary_doc = {
        "id": generate_hash(metadata['url'] + "_summary"),
        "content": metadata["summary"],
        "content_vector": summary_vector,
        "type": "summary",
        "url": metadata['url'],
        "title": metadata['title'],
        "author": metadata['author'],
        "keywords": ", ".join(metadata['keywords']),
        "language": metadata['language'],
        "publisher": metadata['publisher'],
        "content_hash": metadata['content_hash'],
        "timestamp": datetime.now().isoformat()
    }
    
    # Usamos upload_documents (el método nativo)
    client.upload_documents(documents=[summary_doc])
    
    # --- SUBIDA DE LOS CHUNKS ---
    print("[*] Ejecutando Semantic Chunking...")
    chunker = SemanticChunker(embeddings)
    # create_documents devuelve una lista de objetos Document; usamos page_content
    docs = chunker.create_documents([content])
    
    chunk_list = []
    for i, doc in enumerate(docs):
        chunk_text = doc.page_content
        vector = embeddings.embed_query(chunk_text)
        
        chunk_doc = {
            "id": generate_hash(metadata['url'] + str(i)),
            "content": chunk_text,
            "content_vector": vector,
            "type": "chunk",
            "url": metadata['url'],
            "title": metadata['title'],
            "author": metadata['author'],
            "keywords": ", ".join(metadata['keywords']),
            "language": metadata['language'],
            "publisher": metadata['publisher'],
            "content_hash": metadata['content_hash'],
            "timestamp": datetime.now().isoformat()
        }
        chunk_list.append(chunk_doc)
    
    # Subir todos los chunks en un solo lote (batch) para mayor eficiencia
    client.upload_documents(documents=chunk_list)
    print(f"[+] Documento y {len(chunk_list)} chunks subidos exitosamente.")
    
async def run_pipeline(url: str):
    try:
        # Paso 1: Scraping e Ingesta Determinista
        datos_html = await get_html_content_metadata(url)
        if 'error' in datos_html.keys():
            raise PermissionError(f"No fue posible hacer web-scrapping de: {url} \n {datos_html['error']}")
        content_hash = generate_hash(datos_html['content'])
        
        # Verificar que si la url ya se había registrado
        estado = verificar_estado_documento(url, content_hash)
        if estado == "IGUAL":
            print("[*] Contenido sin cambios, saltando.")
        else:
            # Paso 2: Enriquecimiento Cognitivo (LLM)
            metadatos_finales = refine_metadata_with_llm(datos_html)
            metadatos_finales['content_hash'] = content_hash
            print(f"[+] Metadatos completos: {metadatos_finales['title']} (author: {metadatos_finales['author']})")
            if estado == "NUEVO":
                print("[+] URL nueva, indexando...")
                send_2_aisearch(datos_html['content'], metadatos_finales)   
            else:
                print("[!] Contenido modificado, actualizando...")
                # 1. Borrar registros antiguos filtrando por URL
                vector_store.delete(filter=f"url eq '{url}'") 
                # 2. Insertar nuevos
                send_2_aisearch(datos_html['content'], metadatos_finales)
        print("\n=== PRUEBA DE PIPELINE EXITOSA ===")
    except Exception as e:
        print(f"[!] Error en el pipeline: {e}")
        
def verificar_estado_documento(url: str, nuevo_hash: str):
    # Buscamos documentos que tengan esa URL
    # Nota: Asegúrate de que 'url' y 'content_hash' sean filterable=True en Azure
    client = SearchClient(
        endpoint=os.getenv("AZURE_SEARCH_ENDPOINT"),
        index_name=os.getenv("AZURE_SEARCH_INDEX_NAME"),
        credential=AzureKeyCredential(os.getenv("AZURE_SEARCH_KEY"))
    )
    
    # Búsqueda nativa (sin colisiones)
    results = list(client.search(
        search_text="*", 
        filter=f"url eq '{url}'",
        select=["content_hash"]
    ))
    if not results:
        return "NUEVO"
    # Si existe, comparamos el hash
    hash_existente = results[0].get('content_hash')
    
    if hash_existente == nuevo_hash:
        return "IGUAL"
    else:
        return "ACTUALIZAR"
    
async def batch_processor(urls):
    # Limitamos la concurrencia a 5 para no saturar los servicios
        semaphore = asyncio.Semaphore(5)
        
        async def process_with_limit(url):
            async with semaphore:
                await run_pipeline(url)

        tasks = [process_with_limit(url) for url in urls]
        await asyncio.gather(*tasks)
        
if __name__ == "__main__":
    # URL que proporcionaste como ejemplo
    TEST_URL = "https://retinia.mx/agudeza-visual-av/"
    run_pipeline(TEST_URL)