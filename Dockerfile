FROM python:3.11-slim

WORKDIR /app
COPY . .

RUN pip install --no-cache-dir python-telegram-bot==20.7 requests
# instalar Ollama local dentro do container
RUN pip install ollama

EXPOSE 11434

CMD sh -c "ollama serve & python main.py"
