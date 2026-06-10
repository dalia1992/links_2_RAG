# Links2RAG
# Pipeline ETL (Links2RAG)
Dalia Camacho García-Formentí
Proyecto final para Diseño de Infraestructura Escalable
BSG Institute
9 de junio 2026
Repositorio de githu: https://github.com/dalia1992/links_2_RAG.
Video de código y desarrollo: https://drive.google.com/file/d/1ohX3PpQipuFOeOYjX8fmnkns1FE8eKBp/view?usp=sharing 

Video de ejemplificación de consultas a AI Search: https://drive.google.com/file/d/1fipl8B-kTG53onAi6be_QCaHKHaEvURy/view?usp=sharing 

## Pasar links de una lista a una base vectorizada en Azure AI Search

**Objetivo:** Crear un ETL que a partir de archivos .csv o links haga un webscraping para obtener el contenido relevante; posterior a ello extraer metadatos y embeddings. Los cuales se incluirán en una base de Azure AI Search, que pueda ser consultada para incluir links en recomendaciones a usuarios, para que estos consulten las ligas directamente. 


## 1. Guía de Usuario
El objetivo con Links2RAG es crear una base vectorizada a partir del contenido de URLs con lo que sea posible hacer una búsqueda de links relevantes de fuentes validadas.

Con ello posteriormente será posible agregar información de los links a y brindar la referencia específica para consulta a los usuarios de un chat.

El código se encuentra en el repositorio de github: https://github.com/dalia1992/links_2_RAG. 

El caso de uso específico de donde surge el requerimiento es poder incluir ligas de fuentes confiables para robustecer recomendaciones de salud que genera un LLM y pueda redirigir a los usuarios a estas ligas donde la información es más amplia, manteniendo la seguridad de que la fuente es fidedigna.

•	Objetivo: Consultar la base de Azure AI Search para obtener links complementarios para recomendaciones de salud basadas en fuentes consolidadas como la Organización Mundial de la Salud, la American Psychological Association. Así como incluir referencias a blogs creado específicamente para apoyar con algunas recomendaciones específicas.
•	Transparencia: Cada fragmento de información recuperado mantiene trazabilidad directa con su URL original, título, fuente y autor, garantizando que el usuario final reciba fuentes verificadas.
•	Nota de uso: En esta primera fase del proceso ETL, el sistema opera a nivel de backend (base de datos vectorial), sentando los cimientos de infraestructura para una futura integración con una interfaz gráfica orientada al usuario final.

## 2. Guía de Administrador
Para desplegar y operar el pipeline de ingesta masiva, el administrador debe seguir este flujo de aprovisionamiento:

### Fase 0: Requerimientos

1.	Entorno virtual: Crear un entorno virutal con python, en este caso la versión que utilicé fue 3.11.15.
2.	Instalar requerimientos: pip install -r requirements.txt

### Fase 1: Infraestructura en Azure

1.	Azure Foundry: Habilitar modelos de Embeddings (text-embedding-3-small) y Chat (gpt-4.1-mini). 
2.	Azure AI Search: Crear el servicio de búsqueda que alojará el índice vectorial.
3.	Azure Service Bus: Configurar una Cola (Queue) para orquestar la lista de URLs a procesar.
Fase 2: Configuración (.env)

Ejemplo de lo que incluye el .env
# OPENAI CONNECTION
AZURE_OPENAI_API_KEY=XXXXX
AZURE_OPENAI_ENDPOINT=https://XXX-XXX.cognitiveservices.azure.com/

# LLM
DEPLOYMENT_NAME_LLM=gpt-4.1-mini

# EMBEDDINGS
DEPLOYMENT_NAME_EMBEDDINGS=text-embedding-3-small

# AISEARCH
AZURE_SEARCH_ENDPOINT=https://XXXX.search.windows.net
AZURE_SEARCH_KEY=XXXX
AZURE_SEARCH_INDEX_NAME=links_index

# SERVICE BUS
SERVICEBUS_CONNECTION_STR=Endpoint=sb://XXXX
SERVICEBUS_QUEUE_NAME=urls-to-process

### Fase 3: Ejecución
* **Crear Índice Vectorial:** Ejecutar `python -m app.src.create_aisearch` para construir la estructura y el esquema de la base vectorizada.
* **Encolar URLs:** Iniciar el productor (`producer_service_bus.py`).
* **Ingesta Distribuida:** Levantar Workers (`python -m app.scripts.worker_service_bus`) para procesar las colas asíncronamente.

**Nota:** Se puede consultar el video en que explico cuáles son los principales componentes del ETL y lo pongo a correr.
VIDEO

## 3. Caso de Uso
El objetivo principal es la ingesta masiva de URLs institucionales y de salud para construir un motor de búsqueda y recomendaciones.
El pipeline realiza web scraping, enriquece metadatos vía LLMs y genera embeddings, depositando tanto un summary (resumen) como chunks detallados en Azure AI Search.
Esto permite que una futura aplicación RAG ofrezca, junto con sus respuestas, enlaces validados y útiles.
El esquema doble (summary y chunks) está diseñado para que la selección inicial de URLs relevantes se base en la visión general del enlace (el resumen).
Si posteriormente se desea hacer grounding detallado de las respuestas, el sistema puede filtrar sobre esas URLs relevantes y hacer la búsqueda semántica de alta granularidad únicamente en los chunks internos de esos documentos.
<img width="8191" height="1437" alt="CSV Data Processing Workflow-2026-06-10-020806" src="https://github.com/user-attachments/assets/1c64e341-e081-41ff-bdad-27eb2b5fa0de" />

<img width="4406" height="305" alt="CSV Data Processing Workflow-2026-06-10-014733" src="https://github.com/user-attachments/assets/80b1dc14-bb42-42c2-9b68-54c6e946f036" />


## 4. Arquitectura
Se implementó una arquitectura desacoplada y orientada a eventos:

* **Orquestación:** Azure Service Bus para control de mensajes y Dead-Letter Queues.
* **Cómputo:** Workers asíncronos en Python.
* **Bases de Datos:** Azure AI Search como base de datos vectorial nativa para almacenamiento y búsqueda.

## 5. Diseño ETL
El código del ETL está en `src/core_etl.py`

* **Extract:** Sistema híbrido. Usa cloudscraper (con BeautifulSoup) para extracción rápida de etiquetas SEO (OG, Title, Author) y async_playwright en modo Chromium headless para páginas que requieren renderizado JavaScript y cargas perezosas (Lazy Load).
* **Transform:**
  * Identificar contenido relevante desde la extracción, evitar extraer footers o headers que no brindan información sobre el contenido del enlace específico.
  * Sanitización de espacios y saltos de línea con RegEx.
  * Detección automática de errores como 404, 403 o Captchas.
* **Load:** Subida de chunks directo a Azure AI Search (`client.upload_documents`).
<img width="8191" height="1437" alt="CSV Data Processing Workflow-2026-06-10-020806" src="https://github.com/user-attachments/assets/0e7d1275-57d9-45b7-a75d-cb5aabd61e24" />

## 6. Patrones LLM
* **Metadata Enrichment Pattern:** Dado que el scraping determinista no siempre captura buen contexto, se usa AzureChatOpenAI para generar un resumen semántico de 100 palabras, extraer 3 keywords clínicas y deducir el publisher a partir del texto crudo.
* **Semantic Chunking Pattern:** En lugar de dividir por caracteres arbitrarios, se fragmentan los documentos usando SemanticChunker de LangChain Experimental, garantizando que cada chunk retenga significado.

## 7. Resultados de Chunking
El uso del SemanticChunker acoplado al modelo de embeddings permitió dividir páginas complejas respetando la densidad de su información.
El resultado es un índice donde coexisten chunks de detalle y un documento "resumen" (tipo summary) por URL, que facilita búsquedas rápidas.

## 8. Comparación de Embeddings
Se eligió AzureOpenAIEmbeddings generando vectores de dimensión 1536 con text-embedding-3-small.

## 9. Benchmarking de Indexación
La elección de Azure AI Search se justifica por su soporte nativo de búsquedas vectoriales que garantiza una latencia menor.
<img width="4406" height="305" alt="CSV Data Processing Workflow-2026-06-10-014733" src="https://github.com/user-attachments/assets/2ead0dd9-d662-4205-a858-c0fa82b47463" />

Además, su configuración permite metadatos filtrables (`filterable=True`) en campos como URL, Autor, Type y Hash, lo cual es crítico para manejar actualizaciones del pipeline y poder extraer ya sea en links mediante el embedding del resumen o el contenido específico de chunks dentro de una o varias URLs específicas.

## 10. Versionamiento
Para auditar la base de datos documental, el pipeline es idempotente:

* Al leer una URL, se genera un Hash MD5 del texto (`content_hash`).
* Se consulta el índice actual; si el documento no existe se marca como NUEVO.
* Si existe y el hash es idéntico, se marca IGUAL y se omite (ahorrando costos de API).
* Si el hash cambió, se realiza un borrado selectivo (`vector_store.delete(filter=f"url eq '{url}'")`) y se vuelve a insertar, garantizando la frescura de la base de datos.

Además, dentro de los metadatos se guarda la fecha en que se agregó el documento para identificar cuándo se actualizó por última vez en la base vectorizada.

## 11. Observabilidad y Monitoreo
El módulo Worker cuenta con un sistema robusto de métricas registradas en `reporte_procesamiento.csv`.
Por cada URL procesada, se almacena:

* Hora de finalización.
* URL y Estado (ÉXITO/FALLO).
* Tiempo en segundos (`tiempo_procesamiento`).
* Detalle_Error: Para identificar qué error se presentó y poder dar un diagnóstico.

Del total de URLs que se procesaron, el 42.2% se procesó con éxito, mientras que el 57.8% falló en el procesamiento.
Los tipos de errores fueron:

* Access denied: 120
* Page not found: 288
* Captcha required: 0
* No se hizo retrieval de contenido suficiente: 349
* () Unable to get service usage to enforce quota: 4

Se debe revisar el método de scrapping para los casos donde no se hizo retrieval de contenido suficiente, probablemente hay algo por corregir en el proceso.
Sin embargo, los 288 page not found no será posible procesarlos, probablemente por cambio de dominios, ya que la lista inicial de URLs se generó en 2024. Es importante considerar estos cambios, que suelen ocurrir e integrar la eliminación de URLs de la base de conocimiento o agregar una flag de que la página ya no existe, esto para evitar que los usuarios sean dirigidos a páginas inexistentes.

Para los access denied habría que revisar a detalle si es posible hacer modificaciones al webscraping para sobrepasar las restricciones o si no es posible.
El error de service quota puede estar relacionado a que se excedieron las solicitudes a procesar en ese momento.
El tiempo que tomó en promedio procesar los links exitosos fue: 11.9 segundos, el mínimo de 8 segundos y el máximo de 43.4 segundos.
<img width="490" height="512" alt="image" src="https://github.com/user-attachments/assets/35b51950-3eb1-4149-b025-6c64796dca1d" />


## 12. Lecciones Aprendidas
* **Limpieza de Datos:** La extracción de datos y su correcta carga a una base vectorizada es primordial para el éxito de un sistema RAG. Para que la información sea verdaderamente útil para un LLM, es crítico eliminar el "ruido" web (navegación, footers) y espacios adicionales, lo que a su vez disminuye drásticamente los costos por tokens procesados.
* **Potencia de los Metadatos:** Mantener metadatos auxiliares robustos habilita el pre-filtrado en la base vectorizada (por idioma, publisher o tipo de documento), reduciendo el espacio de búsqueda vectorial y mejorando la asertividad del modelo.
* **Escalabilidad y Cuellos de Botella (I/O Bound):** En las pruebas de rendimiento, la ejecución secuencial de 1,307 ligas tomó aproximadamente 4 horas. Aunque el uso de bibliotecas como asyncio demostró ser efectivo en pruebas locales para paralelizar peticiones, la naturaleza del scraping y llamadas de red requiere un verdadero escalado horizontal (Scale-out). La decisión arquitectónica de integrar Azure Service Bus demostró su valor aquí: aunque el despliegue del contenedor Docker en un cluster de Kubernetes para paralelización masiva queda como trabajo futuro, el bus de mensajes garantizó la resiliencia del sistema reteniendo las URLs no procesadas (evitando pérdida de estado) frente a caídas locales. El siguiente paso lógico para optimizar este pipeline es el despliegue de múltiples réplicas del Worker consumiendo la misma cola de Service Bus de forma concurrente.
