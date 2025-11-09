import secretos

# alphavantage api
import requests

# contexto
from albanorama_context import ALBANORAMA_PROYECTO_GUION

# gemini api
from google import genai
from google.genai import types

# Gráficos
import yfinance as yf        
import mplfinance as mpf       
import matplotlib.pyplot as plt

# procesamiento
import json
import pandas as pd
from datetime import datetime, timedelta


def noticias_activo_pre_apertura(nombre_activo, fecha_busqueda):
    # 1A. Definición de Tickers y Clasificación (STOCK vs TOPIC)
    activos_config = {
        "nvidia": {"tipo": "STOCK", "simbolo": "NVDA"},
        "google": {"tipo": "STOCK", "simbolo": "GOOGL"},
        "apple":  {"tipo": "STOCK", "simbolo": "AAPL"},
        "oil":    {"tipo": "TOPIC", "topico": "energy_transportation"},
    }

    #1B. URL para la consulta.
    URL_BASE = "https://www.alphavantage.co/query?"

    # 2. Validación de Entrada
    nombre_activo = nombre_activo.lower()
    if nombre_activo not in activos_config:
        raise ValueError("Ingrese un activo válido.")

    config = activos_config[nombre_activo]
    tipo = config["tipo"]

    # 3. Construcción de los Parámetros de la Consulta
    params = {
        "function": "NEWS_SENTIMENT",
        "apikey": secretos.ALPHAVANTAGE_KEY,
        "time_from": f"{fecha_busqueda}T0000",
        "time_to": f"{fecha_busqueda}T1300",
        "sort": "RELEVANCE",
        "limit": 80
    }

    # 4. Lógica Condicional: Tickers vs. Topics
    if tipo == "STOCK":
        params["tickers"] = config["simbolo"]
        print(f"Buscando noticias de **Stock** para {nombre_activo.upper()} ({config['simbolo']}) en {fecha_busqueda}...")

    elif tipo == "TOPIC":
        params["topics"] = config["topico"]
        print(f"Buscando noticias por **Topic** ({config['topico']}) para {nombre_activo.upper()} en {fecha_busqueda}...")

    else:
        raise ValueError("Ingrese un activo válido.")

    # 5. Lógica Condicional: Tickers vs. Topics
    response = requests.get(URL_BASE, params=params)
    response.raise_for_status()
    datos = response.json()

    # 6. Procesamiento de los Resultados
    for articulo in datos.get('feed', []): # Usar .get() por seguridad
        timestamp_str = articulo['time_published']
        try:
            articulo['time_published_readable'] = datetime.strptime(timestamp_str, '%Y%m%dT%H%M%S').strftime('%Y-%m-%d %H:%M:%S UTC')
        except ValueError:
             articulo['time_published_readable'] = "N/A" # Manejo de error si el formato es inesperado

    df = pd.DataFrame(datos.get('feed', []))

    return df

def noticias_activo(nombre_activo, fecha_busqueda):
    # 1A. Definición de Tickers y Clasificación (STOCK vs TOPIC)
    activos_config = {
        "nvidia": {"tipo": "STOCK", "simbolo": "NVDA"},
        "google": {"tipo": "STOCK", "simbolo": "GOOGL"},
        "apple":  {"tipo": "STOCK", "simbolo": "AAPL"},
        "oil":    {"tipo": "TOPIC", "topico": "energy_transportation"},
    }

    #1B. URL para la consulta.
    URL_BASE = "https://www.alphavantage.co/query?"

    # 2. Validación de Entrada
    nombre_activo = nombre_activo.lower()
    if nombre_activo not in activos_config:
        raise ValueError("Ingrese un activo válido.")

    config = activos_config[nombre_activo]
    tipo = config["tipo"]

    # 3. Construcción de los Parámetros de la Consulta
    params = {
        "function": "NEWS_SENTIMENT",
        "apikey": secretos.ALPHAVANTAGE_KEY,
        "time_from": f"{fecha_busqueda}T0000",
        "time_to": f"{fecha_busqueda}T2359",
        "sort": "RELEVANCE",
        "limit": 80
    }

    # 4. Lógica Condicional: Tickers vs. Topics
    if tipo == "STOCK":
        params["tickers"] = config["simbolo"]
        print(f"Buscando noticias de **Stock** para {nombre_activo.upper()} ({config['simbolo']}) en {fecha_busqueda}...")

    elif tipo == "TOPIC":
        params["topics"] = config["topico"]
        print(f"Buscando noticias por **Topic** ({config['topico']}) para {nombre_activo.upper()} en {fecha_busqueda}...")

    else:
        raise ValueError("Ingrese un activo válido.")

    # 5. Lógica Condicional: Tickers vs. Topics
    response = requests.get(URL_BASE, params=params)
    response.raise_for_status()
    datos = response.json()

    print(datos)

    # 6. Procesamiento de los Resultados
    for articulo in datos.get('feed', []): # Usar .get() por seguridad
        timestamp_str = articulo['time_published']
        try:
            articulo['time_published_readable'] = datetime.strptime(timestamp_str, '%Y%m%dT%H%M%S').strftime('%Y-%m-%d %H:%M:%S UTC')
        except ValueError:
             articulo['time_published_readable'] = "N/A" # Manejo de error si el formato es inesperado

    df = pd.DataFrame(datos.get('feed', []))

    return df

def analizar_relevancia_gemini_masivo_cliente(df_noticias, activo_interes, gemini_client):
    """
    Usa el cliente de Gemini (client.models.generate_content) para clasificar
    la relevancia de todas las noticias en una sola consulta.
    """

    if df_noticias.empty:
        return pd.DataFrame() # Retorna DataFrame vacío si no hay noticias

    #debug:
    #print(f"\n--- 🚀 Analizando {len(df_noticias)} noticias en un solo lote (Baja RPM) ---")

    # 1. Preparar los datos y el esquema
    lista_noticias = []
    for index, row in df_noticias.iterrows():
        lista_noticias.append(f"ID:{index} | Título: {row['title']} | Resumen: {row['summary']}")

    datos_formateados = "\n---\n".join(lista_noticias)

    schema = types.Schema(
        type=types.Type.ARRAY,
        description="Lista de clasificaciones de noticias.",
        items=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "id": types.Schema(type=types.Type.INTEGER, description="El índice ID de la noticia."),
                "relevante": types.Schema(type=types.Type.BOOLEAN, description=f"Verdadero si el artículo trata DIRECTAMENTE sobre la dinámica del activo: {activo_interes}. Falso en caso contrario.")
            },
            required=["id", "relevante"]
        )
    )

    # 2. Definir el prompt
    prompt = f"""
    Eres un analista financiero. Tu tarea es revisar un lote de noticias relacionadas con el sector financiero.
    Para cada artículo, determina si el contenido (Título y Resumen) es **sustancialmente relevante** para la dinámica de precios, la oferta o la demanda del activo '{activo_interes}'.
    
    [Criterios de Relevancia y Irrelevancia omitidos para brevedad]

    Devuelve un array JSON con la clasificación de relevancia para cada noticia, usando el 'ID' que se proporciona.

    Noticias a analizar (ID | Título | Resumen):
    {datos_formateados}
    """

    try:
        # 3. Llamada al modelo usando el objeto client
        response = gemini_client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.0,
                response_mime_type="application/json",
                response_schema=schema
            )
        )

        # 4. Procesar y mapear la respuesta JSON
        clasificaciones = json.loads(response.text)

        relevancia_map = {item['id']: item['relevante'] for item in clasificaciones}

        df_noticias['Relevancia_Gemini'] = df_noticias.index.map(relevancia_map)

        return df_noticias

    except Exception as e:
        print(f"❌ Ocurrió un error al procesar el lote con Gemini: {e}")
        return df_noticias

def generar_analisis_completo(df_relevante, activo_interes, gemini_client):
    """
    Genera el análisis completo del blog (Título, Resumen, Conclusión) e incluye
    las 3 fuentes más importantes para citar.
    """
    if gemini_client is None or df_relevante.empty:
        return None

    print(f"\n--- 📝 Generando análisis y contenido completo con citas para {activo_interes} ---")

    # 1. Formatear los datos CON EL ÍNDICE para que Gemini pueda referenciarlos
    lista_noticias = []
    for index, row in df_relevante.iterrows():
        lista_noticias.append(f"ID:{index} | Título: {row['title']} | Resumen: {row['summary']}")

    datos_formateados = "\n---\n".join(lista_noticias)

    # --- Esquema JSON de Salida FINAL (CON FUENTES) ---
    schema_final = types.Schema(
        type=types.Type.OBJECT,
        properties={
            "Titulo_Blog": types.Schema(type=types.Type.STRING),
            "Conclusion_Contundente": types.Schema(type=types.Type.STRING),
            "Resumen_Blog": types.Schema(type=types.Type.STRING),
            "IDs_Fuentes_Principales": types.Schema(
                type=types.Type.ARRAY,
                description="Los 3 IDs de noticias (índices del DataFrame) que más contribuyeron a la determinación del Sentimiento y el Driver Principal.",
                items=types.Schema(type=types.Type.INTEGER)
            )
        },
        required=["Titulo_Blog", "Conclusion_Contundente", "Resumen_Blog", "IDs_Fuentes_Principales"]
    )

    # 2. Definir el prompt
    prompt_con_citas = f"""
        Eres un analista y editor de blogs experto en el mercado de {activo_interes}.
        Analiza el lote de noticias que ha sido pre-filtrado por impacto (CRÍTICO, MODERADO, NEUTRO) para generar tres elementos cohesivos de contenido financiero.

        **Instrucciones de Análisis y Causalidad (Interno):**
        1.  **Driver Principal:** Identifica el principal impulsor de precios de la noche. Prioriza noticias clasificadas como 'CRÍTICO' y 'MODERADO'.
        2.  **Impacto Global:** Determina si el evento más significativo es CRÍTICO, MODERADO o NEUTRO y devuélvelo en el campo 'Impacto_Global_Estimado'.
        3.  **Causalidad:** Clasifica la Causalidad (CAUSA -> usar 'anticipando' / CONSECUENCIA -> usar 'reaccionando').

        **Formatos Obligatorios:**
        1.  **Titulo_Blog:** Genera un titular profesional, impactante y relevante.
        2.  **Conclusion_Contundente:** Genera la frase única siguiendo el formato estricto: "El mercado del [ACTIVO] está [SENTIMIENTO] [VERBO] [DRIVER PRINCIPAL]."
        3.  **Resumen_Blog:** Genera un párrafo analítico de aproximadamente 100 palabras, detallando la causalidad y el impacto.

        **Instrucciones Adicionales (Citas):**
        Identifica los **3 IDs de noticias (índices)** que fueron los más determinantes para tu análisis de Sentimiento y Driver Principal.

        Noticias a analizar (ID | Título | Impacto | Resumen):
        {datos_formateados}
        """
    try:
        response = gemini_client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt_con_citas,
            config=types.GenerateContentConfig(
                temperature=0.0,
                response_mime_type="application/json",
                response_schema=schema_final
            )
        )

        datos_analisis = json.loads(response.text)

        # 3. Paso final: Agregar la información de la fuente al resultado
        ids_citas = datos_analisis.get("IDs_Fuentes_Principales", [])

        # Filtrar el DataFrame original por los índices más relevantes
        citas_finales_df = df_relevante.loc[df_relevante.index.intersection(ids_citas)][['title', 'url']]
        citas_finales = citas_finales_df.to_dict('records')

        datos_analisis["Fuentes_Citables"] = citas_finales

        return datos_analisis

    except Exception as e:
        print(f"❌ Error al generar el análisis completo: {e}")
        return None

async def obtener_respuesta_asistencia_gemini(pregunta_usuario: str, client) -> str:
    """
    Llama a la API de Gemini para obtener una respuesta basada en el guion del proyecto.
    """
    
    # 1. Combina el guion con la pregunta del usuario para el prompt
    prompt_completo = (
        ALBANORAMA_PROYECTO_GUION + 
        f"\n\n--- PREGUNTA DEL USUARIO ---\n{pregunta_usuario}\n\n"
        "Según el guion de Albanorama, responde a esta pregunta. Sé directo y mantén el tono profesional y humano del proyecto."
    )
    
    try:
        # **Ajusta esta sección a cómo llamas a tu modelo de Gemini**
        # Ejemplo:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt_completo
        )
        return response.text
        
    except Exception as e:
        print(f"Error al llamar a Gemini en asistencia: {e}")
        return "❌ En este momento, no puedo contactar al Asistente de Albanorama. Por favor, inténtalo de nuevo más tarde."

def obtener_precios(
    activo_cons: str,
    fecha_cons: str, # Espera el formato YYYYMMDD
    # Se aumenta el contexto a 1 día antes y 1 día después para un mejor gráfico.
    dias_atras: int = 1, 
    dias_despues: int = 3
) -> pd.DataFrame:
    """
    Descarga precios históricos del activo en intervalos de 1 hora.
    """
    MAPEO_ACTIVOS = {
        "nvidia": "NVDA",
        "google": "GOOGL",
        "apple": "AAPL",
        "oil": "CL=F", # Símbolo para futuros de WTI
    }

    activo = MAPEO_ACTIVOS[activo_cons.lower()]

    # Convertir la fecha de consulta (YYYYMMDD) a objeto datetime
    fecha_T = datetime.strptime(fecha_cons, '%Y%m%d')

    # Definir el rango de descarga (incluyendo días antes/después)
    fecha_inicio_descarga = fecha_T - timedelta(days=dias_atras)
    # yfinance excluye la fecha de fin, por eso se añade 1 día extra al final.
    fecha_fin_descarga = fecha_T + timedelta(days=dias_despues + 1)

    start_date = fecha_inicio_descarga.strftime('%Y-%m-%d')
    end_date = fecha_fin_descarga.strftime('%Y-%m-%d')

    print(f'\nDescargando precios de {activo} desde {start_date} hasta {end_date}')

    data = yf.download(
                tickers=activo,
                start=start_date,
                end=end_date,
                interval='1h',
                rounding=True,
                multi_level_index=False,
                progress=False
                )
    
    return data



    # Renombrar columnas para compatibilidad con mplfinance (yfinance usa mayúsculas)
    #data.columns = [col.capitalize().replace(' ', '') for col in data.columns]
    # Asegurar que el nombre de la columna de cierre es 'Close'
    #if 'AdjClose' in data.columns:
    #    data.rename(columns={'AdjClose': 'Close'}, inplace=True)
        
    #return data[['Open', 'High', 'Low', 'Close', 'Volume']]


def grafico_precios_guardar_imagen(precios, activo_cons, fecha_cons, filename='chart.png'):
    """
    Genera un gráfico de velas y lo guarda en un archivo PNG.
    Se reduce el DPI a 150 para mantener el tamaño del archivo bajo.
    """
    # --- 1. Preparación de Variables ---
    MAPEO_ACTIVOS = {
        "nvidia": "NVDA",
        "google": "GOOGL",
        "apple": "AAPL",
        "oil": "CL=F (WTI)",
    }
    activo_simbolo = MAPEO_ACTIVOS.get(activo_cons.lower(), activo_cons)
    fecha_T = datetime.strptime(fecha_cons, '%Y%m%d')
    fecha_legible = fecha_T.strftime('%Y-%m-%d')

    # --- 2. Definición de Estilo ---
    # Estilo optimizado para un fondo oscuro como Discord
    color_up = '#78CDD7' # Verde/Teal
    color_down = '#0D5C63' # Rojo
    
    mc = mpf.make_marketcolors(
        up=color_up,
        down=color_down,
        edge=color_down,
        volume='in', 
        ohlc='i'
    )
    # Usar un estilo base oscuro y aplicar los colores personalizados
    custom_style = mpf.make_mpf_style(marketcolors=mc)

    # --- 3. Trazado y Guardado del Gráfico ---
    mpf.plot(
        precios,
        type='candle',
        volume=True,
        style=custom_style,
        title=f'{activo_simbolo} - Velas de 1h | Centro: {fecha_legible}',
        ylabel='Precio',
        figratio=(15, 8),
        figscale=0.8,
        # ** Parámetro de guardado clave para Discord **
        savefig=dict(fname=filename, dpi=150, bbox_inches='tight') 
    )

    # Asegúrate de cerrar la figura de Matplotlib para liberar memoria (MUY IMPORTANTE)
    plt.close('all')
    
    return filename