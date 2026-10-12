# Imagem de produção do Portal de Análise de Concorrência.
# Inclui as bibliotecas de sistema que o WeasyPrint precisa para montar o
# PDF (Pango, Cairo, GDK-Pixbuf) — sem elas, a geração do relatório falha
# ao importar weasyprint.
#
# Nome do pacote GDK-Pixbuf: em versões mais recentes do Debian (base desta
# imagem, atualizada pela própria Docker Hub com o tempo) o pacote se chama
# libgdk-pixbuf-2.0-0 (com hífen antes do "2.0"); em versões mais antigas
# era libgdk-pixbuf2.0-0 (sem hífen, com ponto). Como a tag "slim" é
# atualizada sem aviso e pode trocar de versão do Debian a qualquer
# momento, instalamos com "|| apt-get install" cobrindo os dois nomes, em
# vez de travar o build quando o nome mudar de novo no futuro.
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libffi-dev \
    fonts-liberation \
    && (apt-get install -y --no-install-recommends libgdk-pixbuf-2.0-0 \
        || apt-get install -y --no-install-recommends libgdk-pixbuf2.0-0) \
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
