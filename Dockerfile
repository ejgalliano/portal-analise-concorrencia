# Imagem de produção do Portal de Análise de Concorrência.
# Inclui as bibliotecas de sistema que o WeasyPrint precisa para montar o
# PDF (Pango, Cairo, GDK-Pixbuf) — sem elas, a geração do relatório falha
# ao importar weasyprint.
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf2.0-0 \
    libffi-dev \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN mkdir -p orders

# Railway/Render injetam a porta real na variável PORT.
ENV PORT=8000
EXPOSE 8000

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
