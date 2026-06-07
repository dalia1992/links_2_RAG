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

def get_html_metadata(url: str) -> dict:
    """
    Descarga el HTML y extrae metadatos SEO básicos de forma determinista.
    """
    print(f"[*] Descargando HTML de: {url}")
    soup = None
    idioma = "Desconocido"
    titulo = "Desconocido"
    autor = "Desconocido"
    descripcion = ""
    
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
        idioma = html_tag.get('lang', 'Desconocido') if html_tag else 'Desconocido'
        
        og_title = soup.find('meta', property='og:title')
        title_tag = soup.find('title')
        titulo = og_title['content'] if og_title else (title_tag.get_text() if title_tag else "Desconocido")
        
        author_meta = soup.find('meta', attrs={'name': 'author'})
        autor = author_meta['content'] if author_meta else "Desconocido"
        
        desc_meta = soup.find('meta', attrs={'name': 'description'}) or soup.find('meta', property='og:description')
        descripcion = desc_meta['content'] if desc_meta else ""

    return {
        "idioma": idioma,
        "titulo": titulo,
        "autor": autor,
        "descripcion_previa": descripcion
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
            # Y opcionalmente, agrega una pequeña espera inteligente:
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
            texto_final.strip()
            
            await browser.close()
    except Exception as e:
        print(f"[!] Error al renderizar con Playwright: {e}")
        texto_final = ""
        
    return texto_final

async def get_html_content_metadata(url: str) -> dict:
    metadata = get_html_metadata(url)
    content = await extract_html_content(url)
    access_errors = ["access denied", "forbidden", "don't have permission"]
    if any(err in content.lower() for err in access_errors):
        metadata['error'] = 'access denied'
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
    print("[*] Ejecutando análisis cognitivo con gpt-4o-mini...")
    
    prompt = f"""
    Eres un asistente médico experto. Analiza este texto y genera ÚNICAMENTE un objeto JSON válido.
    
    Ya tenemos estos datos extraídos de la web:
    - URL: {datos_html['url']}
    - Título: {datos_html['titulo']}
    - Autor: {datos_html['autor']}
    - Descripción SEO: {datos_html['descripcion_previa']}
    
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

async def run_pipeline(url: str):
    try:
        # Paso 1: Scraping e Ingesta Determinista
        datos_html = await get_html_content_metadata(url)
        content_hash = generate_hash(datos_html['content'])
        print(f"[+] Datos extraídos. Hash: {content_hash}")
        
        # Paso 2: Enriquecimiento Cognitivo (LLM)
        metadatos_finales = refine_metadata_with_llm(datos_html)
        print(f"[+] Metadatos completos: {metadatos_finales['titulo']} (Autor: {metadatos_finales['autor']})")
        
        # Paso 3: Semantic Chunking
        print("[*] Ejecutando Semantic Chunking...")
        chunker = SemanticChunker(embeddings)
        chunks = chunker.create_documents([datos_html['content']])
        print(f"[+] Documento dividido en {len(chunks)} chunks semánticos.")
        for i, chunk in enumerate(chunks[:3]):
            print(f"--- Chunk {i+1} ---")
            print(f"Longitud: {len(chunk.page_content)} caracteres")
            print(f"Contenido: {chunk.page_content}")
            print("\n")
        
        print("\n=== PRUEBA DE PIPELINE EXITOSA ===")
        print(json.dumps(metadatos_finales, indent=2, ensure_ascii=False))

    except Exception as e:
        print(f"[!] Error en el pipeline: {e}")

if __name__ == "__main__":
    # URL que proporcionaste como ejemplo
    TEST_URL = "https://retinia.mx/agudeza-visual-av/"
    run_pipeline(TEST_URL)