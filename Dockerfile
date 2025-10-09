# Estágio 1: Build
# Usa uma imagem base completa do Python para instalar dependências
FROM python:3.11-slim AS builder

# Define o diretório de trabalho
WORKDIR /app

# Instala dependências do sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copia os arquivos de dependência e instala-os
COPY requirements.txt .

# Instala dependências em um ambiente virtual
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt



FROM python:3.11-slim AS production

WORKDIR /app

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

ENV PYTHONPATH=/app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN mkdir -p /app/state /app/logs /app/pdfs

COPY src /app/src
COPY data /app/data
COPY tests /app/tests
COPY *.py /app/
COPY *.sh /app/
COPY requirements.txt /app/

RUN chmod +x /app/*.sh

USER nobody

CMD ["gunicorn", "-k", "uvicorn.workers.UvicornWorker", "-w", "4", "-b", "0.0.0.0:8000", "buscador.app_new:app"]
