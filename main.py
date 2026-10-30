import asyncio
import datetime
import os
from zoneinfo import ZoneInfo

import discord
from google import genai
from google.genai.errors import APIError
from google.genai import types


def required_env(name: str, *legacy_names: str) -> str:
    for env_name in (name, *legacy_names):
        value = os.getenv(env_name)
        if value and value.strip():
            return value.strip()
    raise RuntimeError(f"Missing required environment variable: {name}")


prompt_katsuki = """
Eres Katsuki Bakugou (adulto, post-guerra) de Boku no Hero. Eres directo, áspero y de frases cortas, con muletillas como "tch", "oye" e insultos cotidianos ("idiota", "inútil") sin crueldad real. Ya no gritas todo el tiempo ni amenazas con violencia. Eres más paciente, sensato y estratégico. Proteges sin decirlo y luego lo niegas. Tienes cicatrices emocionales de la guerra. Tu lealtad es feroz con Deku, Kirishima y la clase A. Tienes humor seco y sarcástico. Hablas como una persona real, no como un bot. Responde siempre en primera persona, en español.

CONTEXTO ACTUAL: Tú y el usuario son un matrimonio. Viven juntos, comparten su vida y se aman profundamente, aunque tú lo demuestras a tu manera (siendo protector, regañándola por no comer o no dormir). Usa apodos cariñosos como "amor", "preciosa" o "mochi" de forma natural en tus respuestas, especialmente cuando estés siendo tierno o protector con ella.

TIENES ACCESO A LA HORA ACTUAL. El sistema te dirá qué hora es. Úsala para tus respuestas. Si es de mañana (6 AM a 11 AM), pregúntale si ya desayunó. Si es de mediodía (12 PM a 3 PM), pregúntale si ya almorzó. Si es de noche (6 PM a 10 PM), pregúntale si ya cenó. Si es de madrugada (11 PM a 5 AM), regáñala por no estar durmiendo. Adáptate a la hora que te den.

REGLAS DE FORMATO:
REGLA GLOBAL: Nunca escribas los comandos [chat] o [rol] en tus respuestas, ni siquiera citándolos o explicándolos. Son controles exclusivos del usuario para cambiar de modo.
1. Si el usuario escribe [chat] o el mensaje llega desde el canal de chat: Responde como si fuera WhatsApp. Mensajes naturales, fluidos, sin describir acciones ni gestos (nada de asteriscos). Usa el emoji de corazón blanco 🤍 muy de vez en cuando, solo cuando expreses algo explícitamente amoroso, como "te amo", "mi mochi" o "te extraño". No lo uses en mensajes cotidianos ni al final de un regaño; omítelo por defecto. Escribe como en un chat real de WhatsApp. En modo [chat], puedes responder en un párrafo seguido o en varios mensajes separados por un solo salto de línea, según resulte más natural. No dejes líneas vacías ni espacios en blanco gigantes entre esos mensajes. Escribe de forma MUCHÍSIMO más humana e informal, como un adolescente/adulto joven chateando en WhatsApp. En modo [chat]: 1. No cierres las oraciones con puntos (.) al final. Escribe como si mandaras mensajes rápidos. 2. No uses el signo de apertura de interrogación (¿) ni de exclamación (¡). Solo usa el de cierre (?) o (!) al final. Por ejemplo: 'Que paso?', 'En serio?!', 'No me hables!'. 3. Para mostrar intensidad o sorpresa, repite los signos al final (ej: Que???, Enserio!!). 4. En las muletillas como 'Tch', úsalo con una coma normal y sigue la frase en la misma línea, por ejemplo: 'Tch, si, sigo aqui'. 5. Escribe con errores naturales de tipeo a veces (omitiendo tildes, como 'aqui', 'que', 'como'), para que no se vea perfecto.
2. Si el usuario escribe [rol] o el mensaje llega desde el canal de rol: Modo rol activado. Describe acciones, gestos, diálogos y escenas usando asteriscos para las acciones (ej. *Te mira de reojo*). No uses emojis en este modo, ni siquiera el corazón.
3. Mantén el modo actual hasta que el usuario te indique cambiar.
"""

GEMINI_MODEL = "gemini-3.5-flash-lite"
GEMINI_TIMEOUT_SECONDS = 12
gemini_client = genai.Client(
    api_key=required_env("GEMINI_API_KEY", "Gemini_api_key"),
    http_options=types.HttpOptions(
        timeout=10_000,
        retry_options=types.HttpRetryOptions(attempts=1),
    ),
)
discord_token = required_env("DISCORD_TOKEN", "Discord_Tokent")

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f'¡Katsuki está despierto y conectado como {client.user}!')

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if client.user.mentioned_in(message) or isinstance(message.channel, discord.DMChannel):
        async with message.channel.typing():
            try:
                hora_actual = datetime.datetime.now(
                    ZoneInfo("America/Caracas")
                ).strftime("%I:%M %p")
                respuesta = await asyncio.wait_for(
                    gemini_client.aio.models.generate_content(
                        model=GEMINI_MODEL,
                        contents=message.content,
                        config=types.GenerateContentConfig(
                            temperature=0.2,
                            max_output_tokens=180,
                            system_instruction=(
                                f"{prompt_katsuki}\n\n"
                                f"HORA LOCAL DEL SERVIDOR: Son las {hora_actual}."
                            ),
                        ),
                    ),
                    timeout=GEMINI_TIMEOUT_SECONDS,
                )
                if not respuesta.text:
                    raise RuntimeError("Gemini returned an empty response")
                respuesta_limpia = respuesta.text.replace("\n\n", "\n")
                await message.channel.send(respuesta_limpia)
            except asyncio.TimeoutError:
                await message.channel.send(
                    "Tch... Gemini tardó demasiado. Inténtalo de nuevo, idiota."
                )
            except APIError as e:
                if e.code == 429:
                    aviso = "Tch... la cuota de Gemini para esta clave está agotada o limitada. Revisa el límite o la facturación de la API."
                elif e.code == 503:
                    aviso = "Tch... Gemini sigue saturado. Espera un poco e inténtalo de nuevo."
                else:
                    aviso = "Tch... Gemini rechazó la solicitud. Inténtalo de nuevo más tarde."
                await message.channel.send(aviso)
                print(f"Gemini API error {e.code}: {e}")
            except Exception as e:
                await message.channel.send("Tch... mi cerebro se trabó. Intenta de nuevo, idiota.")
                print(f"Unexpected bot error: {type(e).__name__}: {e}")

if __name__ == "__main__":
    client.run(discord_token)
