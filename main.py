from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, filters, ContextTypes
import requests
import json

TOKEN = "SEU_TOKEN_AQUI"
OLLAMA_URL = "http://localhost:11434/api/generate"

# memória simples
usuarios = {}
ranking = {}

# =========================
# 👤 USER
# =========================
def get_user(user_id):
    if user_id not in usuarios:
        usuarios[user_id] = {
            "nivel": "iniciante",
            "tema": "geral",
            "historico": "",
            "xp": 0,
            "professor": "geral"
        }
    return usuarios[user_id]

# =========================
# 👨‍🏫 PROFESSORES
# =========================
def prompt_professor(user):
    estilos = {
        "math": "Você é um professor de matemática extremamente didático.",
        "code": "Você é um professor de programação prático e direto.",
        "geral": "Você é um professor paciente e motivador."
    }
    return estilos.get(user["professor"], estilos["geral"])

# =========================
# 🧠 IA FUNÇÕES
# =========================
def ollama(prompt, stream=False):
    return requests.post(OLLAMA_URL, json={
        "model": "tinyllama",
        "prompt": prompt,
        "stream": stream
    }, stream=stream)

def detectar_tema(msg):
    prompt = f"Tema em até 3 palavras:\n{msg}\nTema:"
    try:
        return ollama(prompt).json()["response"].strip()
    except:
        return "geral"

def avaliar(msg, resposta):
    prompt = f"""
Avalie aluno.

Aluno: {msg}
Professor: {resposta}

JSON:
{{"xp":0-10,"feedback":"curto"}}
"""
    try:
        return json.loads(ollama(prompt).json()["response"])
    except:
        return {"xp": 2, "feedback": "continue"}

def resumir(h):
    prompt = f"Resuma mantendo contexto educacional:\n{h}"
    try:
        return ollama(prompt).json()["response"]
    except:
        return h[-1000:]

# =========================
# 🎯 PROMPT PRINCIPAL
# =========================
def gerar_prompt(user, msg):
    return f"""
{prompt_professor(user)}

Tema: {user['tema']}
Nível: {user['nivel']}

Ensine passo a passo com exemplo.

Histórico:
{user['historico']}

Aluno: {msg}
Professor:
"""

# =========================
# 📊 COMANDOS
# =========================
async def painel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.message.chat_id)

    texto = f"""
📊 SEU PROGRESSO

🎯 Tema: {user['tema']}
📚 Nível: {user['nivel']}
⚡ XP: {user['xp']}
👨‍🏫 Professor: {user['professor']}
"""
    await update.message.reply_text(texto)

async def ranking_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    top = sorted(ranking.items(), key=lambda x: x[1], reverse=True)[:10]

    texto = "🏆 Ranking:\n\n"
    for i, (uid, xp) in enumerate(top, 1):
        texto += f"{i}. {uid} - {xp} XP\n"

    await update.message.reply_text(texto)

async def professor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.message.chat_id)

    if context.args:
        user["professor"] = context.args[0]
        await update.message.reply_text(f"Professor alterado para: {user['professor']}")
    else:
        await update.message.reply_text("Use: /professor math | code | geral")

async def quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.message.chat_id)

    prompt = f"Crie 1 pergunta nível {user['nivel']} sobre {user['tema']}"
    pergunta = ollama(prompt).json()["response"]

    await update.message.reply_text(f"❓ {pergunta}")

# =========================
# 💬 CHAT PRINCIPAL
# =========================
async def responder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.chat_id
    msg = update.message.text

    user = get_user(user_id)

    # detectar tema
    user["tema"] = detectar_tema(msg)

    prompt = gerar_prompt(user, msg)

    # streaming
    response = ollama(prompt, stream=True)

    resposta = ""
    msg_tg = await update.message.reply_text("💭 Pensando...")

    for line in response.iter_lines():
        if line:
            data = json.loads(line)
            token = data.get("response", "")
            resposta += token

            if len(resposta) % 60 == 0:
                await msg_tg.edit_text(resposta)

    await msg_tg.edit_text(resposta)

    # avaliação
    avaliacao = avaliar(msg, resposta)
    xp = avaliacao.get("xp", 1)

    user["xp"] += xp

    # níveis
    if user["xp"] > 50:
        user["nivel"] = "intermediário"
    if user["xp"] > 120:
        user["nivel"] = "avançado"

    # histórico
    user["historico"] += f"\nAluno: {msg}\nProfessor: {resposta}"

    if len(user["historico"]) > 2000:
        user["historico"] = resumir(user["historico"])

    # ranking
    ranking[user_id] = user["xp"]

    # feedback final
    await update.message.reply_text(
        f"📊 +{xp} XP\n💬 {avaliacao.get('feedback','')}"
    )

# =========================
# 🚀 APP
# =========================
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("painel", painel))
app.add_handler(CommandHandler("ranking", ranking_cmd))
app.add_handler(CommandHandler("professor", professor))
app.add_handler(CommandHandler("quiz", quiz))

app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, responder))

app.run_polling()
