# bibliotecas previas

# discord
import discord
from discord.ext import commands

# gemini api
from google import genai
from google.genai import types


# api-keys
import secretos

# contexto
import albanorama_context

# procesamiento
import requests
import pandas as pd
from datetime import datetime, timedelta
import json
import os

# funciones del bot
from funciones import *
#analizar_relevancia_gemini_masivo_cliente, noticias_activo_pre_apertura, generar_analisis_completo, obtener_respuesta_asistencia_gemini, noticias_activo

#--------------------------------------------
# Configurar el bot

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='$',intents=intents)
#--------------------------------------------
# Cliente de Gemini para análisis.
try:
    # Usar la clave de API para inicializar el cliente
    gemini_client = genai.Client(api_key=secretos.GEMINI_KEY)
except ImportError:
    print("ADVERTENCIA: No se pudo importar la librería 'google-genai'. El comando no funcionará.")
    gemini_client = None
except Exception as e:
    print(f"ERROR: No se pudo inicializar el cliente Gemini. Asegúrate de que la clave sea válida. Error: {e}")
    gemini_client = None

#--------------------------------------------
# Acción al inicio de la ejecución
@bot.event
async def on_ready():
    print(f"¡Me he activado! ¿En qué les puedo ayudar? {bot.user}")

# Comando para testear:
@bot.command()
async def repeat(ctx, *args):
    res = ' '.join(args)
    await ctx.send(res)

# Comando para las noticias influyentes de la apertura de NY
@bot.command()
async def pre_apertura_usa(ctx, activo_consultar: str):
    """
    Proporciona un análisis del mercado pre-apertura para un activo específico.
    Uso: $PreAperturaUSA [activo] (e.g., $PreAperturaUSA oil)
    """
    ## Validar el cliente de Gemini
    #if gemini_client is None:
    #    await ctx.send("❌ **Error de Configuración:** El cliente Gemini no está inicializado. Por favor, revisa tu clave de API.")
    #    return

    # Validar activo
    activo_consultar = activo_consultar.lower()
    if activo_consultar not in ['oil', 'google', 'apple', 'nvidia']:
        await ctx.send("❌ **Error de Activo:** Por favor, use un activo válido: `oil`, `google`, `apple`, `nvidia`.")
        return

    # 1. Determinar la fecha de ayer
    # Para obtener noticias del cierre de ayer al pre-apertura de hoy, se consulta el día anterior.
    ayer = datetime.now() - timedelta(days=5)
    hoy = datetime.now()
    fecha_busqueda = ayer.strftime('%Y%m%d') # Formato AAAA MM DD

    await ctx.send(f"🔍 Buscando y analizando noticias de **{activo_consultar.upper()}**. Esto podría tardar unos segundos, por favor espere...")

    async with ctx.typing():

	    try:
	        # 2. Ejecutar la cadena de funciones
	        noticias = noticias_activo_pre_apertura(activo_consultar, fecha_busqueda)

	        if noticias.empty:
	            await ctx.send(f"ℹ️ No se encontraron noticias relevantes de **{activo_consultar.upper()}**. Parece que fué un día tranquilo.")
	            return

	        df_analizado_final = analizar_relevancia_gemini_masivo_cliente(noticias, activo_consultar, gemini_client)

	        # Filtrar solo las noticias relevantes para el análisis final
	        df_relevante = df_analizado_final[df_analizado_final['Relevancia_Gemini'] == True].copy()
	        
	        if df_relevante.empty:
	            await ctx.send(f"ℹ️ No se encontraron noticias *relevantes* de **{activo_consultar.upper()}** para el análisis. Parece que fué un día tranquilo.")
	            return


	        resultado = generar_analisis_completo(df_relevante, activo_consultar, gemini_client)

	        # 3. Formatear la respuesta para Discord
	        if resultado:
	            # Crear un Embed elegante para Discord
	            embed = discord.Embed(
	                title=resultado['Titulo_Blog'],
	                description=f"**Activo:** {activo_consultar.upper()} | **Fecha de Análisis:** {ayer.strftime('%Y-%m-%d')}",
	                color=discord.Color.blue()
	            )

	            # Campo 1: Conclusión Contundente
	            embed.add_field(
	                name="💥 Conclusión del Análisis (Driver Principal)",
	                value=f"**{resultado['Conclusion_Contundente']}**",
	                inline=False
	            )

	            # Campo 2: Resumen
	            embed.add_field(
	                name="📰 Resumen del Mercado Pre-Apertura",
	                value=resultado['Resumen_Blog'],
	                inline=False
	            )

	            # Campo 3: Fuentes
	            fuentes_text = "\n".join([
	                f"[{i+1}. {c['title']}]({c['url']})" 
	                for i, c in enumerate(resultado.get('Fuentes_Citables', []))
	            ])
	            
	            if fuentes_text:
	                 embed.add_field(
	                    name="🔗 Fuentes Principales Citadas",
	                    value=fuentes_text,
	                    inline=False
	                )

	            await ctx.send(embed=embed)
	        
	        else:
	            await ctx.send("❌ **Error Interno:** No se pudo generar el análisis final. Por favor, inténtalo de nuevo.")


	    except requests.exceptions.HTTPError as e:
	        await ctx.send(f"⚠️ **Error de API (Alpha Vantage):** Fallo al obtener datos. Código de estado: `{e.response.status_code}`.")
	    except Exception as e:
	        # Captura cualquier otro error, como un error de Gemini o de pandas
	        print(f"Error general en el comando PreAperturaUSA: {e}")
	        await ctx.send(f"❌ **Error Desconocido:** Ocurrió un error inesperado al procesar la solicitud. `{e}`")

    await ctx.send("¡Espero haberte sido de ayuda!\n")

# Asistencia del bot
@bot.command(name='asistencia', help='Consulta al Asistente de Albanorama sobre cualquier tema relacionado con el mercado y la plataforma.')
async def asistencia(ctx, *, consulta: str):
    """
    Responde a la consulta del usuario utilizando la IA de Gemini
    con el guion de Albanorama como contexto.
    """
    async with ctx.typing():

    	try:
	    	# 2. Obtiene la respuesta de Gemini
	    	# La función usará el guion como contexto
		    respuesta_gemini = await obtener_respuesta_asistencia_gemini(consulta, gemini_client)

	    	# 3. Crea el Discord Embed
		    embed = discord.Embed(
		        title=f"💡 Asistente de Albanorama Responde:",
		        description=respuesta_gemini,
		        color=0x4F9B77 # Un color que se sienta profesional (ej: verde bosque)
		    )
		    embed.set_footer(text="Albanorama: Gracias por preferirnos.")
    		
		    # 4. Envía la respuesta
		    await ctx.send(embed=embed)

    	except Exception as e:
        	print(f"Error en el comando asistencia: {e}")
        	await ctx.send(f"⚠️ **Error del Bot:** Lo siento, ocurrió un problema al procesar tu solicitud: `{e}`")


@bot.command()
async def analisis_historico(ctx, fecha_consulta: str, activo_consultar: str):
    """
    Proporciona un análisis histórico del mercado para un activo en una fecha específica.
    Uso: $analisis_historico [AAAA-MM-DD] [activo] (e.g., $analisis_historico 2025-03-15 oil)
    """
    # 1. Validar el cliente de Gemini
    if gemini_client is None:
        await ctx.send("❌ **Error de Configuración:** El cliente Gemini no está inicializado. Por favor, revisa tu clave de API.")
        return

    # 2. Validar la fecha
    try:
        # Intentar parsear la fecha en formato YYYY-MM-DD
        fecha_obj = datetime.strptime(fecha_consulta, '%Y-%m-%d')
        # Convertir a formato YYYYMMDD para la API de Alpha Vantage
        fecha_busqueda = fecha_obj.strftime('%Y%m%d')
        # Formato legible para el embed final
        fecha_legible = fecha_obj.strftime('%Y-%m-%d')

        print(type(fecha_busqueda))
    except ValueError:
        await ctx.send("❌ **Error de Formato de Fecha:** Por favor, use el formato `AAAA-MM-DD` (ej: `2025-03-15`).")
        return

    # 3. Validar activo (similar a pre_apertura_usa)
    activo_consultar = activo_consultar.lower()
    if activo_consultar not in ['oil', 'google', 'apple', 'nvidia']:
        await ctx.send("❌ **Error de Activo:** Por favor, use un activo válido: `oil`, `google`, `apple`, `nvidia`.")
        return

    await ctx.send(f"🔍 Buscando y analizando noticias históricas de **{activo_consultar.upper()}** para el **{fecha_legible}**. Esto podría tardar unos segundos, por favor espere...")

    async with ctx.typing():
        try:
            # 4. Ejecutar la cadena de funciones
            # NOTA: Usaremos una versión modificada de la función de noticias para el rango histórico completo.
            noticias = noticias_activo(activo_consultar, fecha_busqueda)

            if noticias.empty:
                await ctx.send(f"ℹ️ No se encontraron noticias relevantes de **{activo_consultar.upper()}** para el **{fecha_legible}**. Parece que fue un día tranquilo.")
                return

            # 5. Análisis de relevancia (Reutilizamos las funciones de Gemini)
            df_analizado_final = analizar_relevancia_gemini_masivo_cliente(noticias, activo_consultar, gemini_client)
            df_relevante = df_analizado_final[df_analizado_final['Relevancia_Gemini'] == True].copy()
            
            if df_relevante.empty:
                await ctx.send(f"ℹ️ No se encontraron noticias *relevantes* de **{activo_consultar.upper()}** para el análisis en **{fecha_legible}**.")
                return

            # 6. Generación del análisis final
            resultado = generar_analisis_completo(df_relevante, activo_consultar, gemini_client)

            # 7. Formatear la respuesta para Discord (Embed)
            if resultado:
                embed = discord.Embed(
                    title=resultado['Titulo_Blog'],
                    description=f"**Activo:** {activo_consultar.upper()} | **Fecha de Análisis Histórico:** {fecha_legible}",
                    color=discord.Color.green() # Usar un color diferente para histórico
                )

                # Campo 1: Conclusión Contundente
                embed.add_field(
                    name="💥 Conclusión del Análisis Histórico (Driver Principal)",
                    value=f"**{resultado['Conclusion_Contundente']}**",
                    inline=False
                )

                # Campo 2: Resumen
                embed.add_field(
                    name="📰 Resumen Histórico del Mercado",
                    value=resultado['Resumen_Blog'],
                    inline=False
                )

                # Campo 3: Fuentes
                fuentes_text = "\n".join([
                    f"[{i+1}. {c['title']}]({c['url']})" 
                    for i, c in enumerate(resultado.get('Fuentes_Citables', []))
                ])
                
                if fuentes_text:
                     embed.add_field(
                         name="🔗 Fuentes Principales Citadas",
                         value=fuentes_text,
                         inline=False
                     )

                await ctx.send(embed=embed)
            
            else:
                await ctx.send("❌ **Error Interno:** No se pudo generar el análisis final. Por favor, inténtalo de nuevo.")


        except requests.exceptions.HTTPError as e:
            await ctx.send(f"⚠️ **Error de API (Alpha Vantage):** Fallo al obtener datos. Código de estado: `{e.response.status_code}`.")
        except Exception as e:
            print(f"Error general en el comando analisis_historico: {e}")
            await ctx.send(f"❌ **Error Desconocido:** Ocurrió un error inesperado al procesar la solicitud. `{e}`")

    await ctx.send("¡Análisis histórico completado!\n")

# Comandos de gráficos
@bot.command()
async def grafico_historico(ctx, fecha_consulta: str, activo_consultar: str):
    """
    Genera y envía un gráfico de velas de 1h para un activo en una fecha específica.
    Uso: $grafico_historico [AAAA-MM-DD] [activo] (e.g., $grafico_historico 2025-03-15 oil)
    """
    activo_consultar = activo_consultar.lower()
    file_name = 'chart.png'

    # 1. Validar activo
    if activo_consultar not in ['oil', 'google', 'apple', 'nvidia']:
        await ctx.send("❌ **Error de Activo:** Por favor, use un activo válido: `oil`, `google`, `apple`, `nvidia`.")
        return

    # 2. Validar y formatear la fecha
    try:
        # Intenta parsear la fecha en formato YYYY-MM-DD
        datetime.strptime(fecha_consulta, '%Y-%m-%d')
        # Convierte a formato YYYYMMDD para la función interna (sin guiones)
        fecha_busqueda = fecha_consulta.replace('-', '')
        fecha_legible = fecha_consulta
    except ValueError:
        await ctx.send("❌ **Error de Formato de Fecha:** Por favor, use el formato `AAAA-MM-DD` (ej: `2025-03-15`).")
        return

    await ctx.send(f"📈 Descargando y generando gráfico de **{activo_consultar.upper()}** para la fecha **{fecha_legible}**. Esto podría tardar unos segundos...")

    async with ctx.typing():
        try:
            # 3. Descargar precios (incluye 1 día antes y 1 día después para contexto)
            precios_df = obtener_precios(activo_consultar, fecha_busqueda)

            if precios_df.empty:
                await ctx.send(f"⚠️ **Error de Datos:** No se encontraron datos de precios de **{activo_consultar.upper()}** en las fechas cercanas a **{fecha_legible}**. El mercado puede haber estado cerrado o no hay datos disponibles.")
                return

            # 4. Generar y guardar el gráfico
            grafico_precios_guardar_imagen(precios_df, activo_consultar, fecha_busqueda, filename=file_name)

            # 5. Enviar el archivo a Discord
            # 5A. Crear el objeto discord.File (sin usar el bloque 'with')
            discord_file = discord.File(file_name) 
            
            # 5B. Enviar el archivo
            await ctx.send(file=discord_file)

            await ctx.send("Gráfico histórico enviado con éxito. ¡Espero que te sea útil!")
        except Exception as e:
            print(f"Error general en el comando grafico_historico: {e}")
            await ctx.send(f"❌ **Error Desconocido:** Ocurrió un error inesperado al procesar la solicitud del gráfico. `{e}`")

        finally:
            # 6. Limpieza: Asegurarse de eliminar el archivo localmente después de enviarlo.
            # Esto es vital para no saturar la memoria del servidor.
            if os.path.exists(file_name):
                os.remove(file_name)

#--------------------------------------------
# Activar el bot
bot.run(secretos.DISCORD_KEY)
