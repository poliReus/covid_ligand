# Usa una base Ubuntu stabile
FROM ubuntu:22.04

# Evita interazioni durante l'installazione
ENV DEBIAN_FRONTEND=noninteractive

# Installa dipendenze di sistema: OpenMPI, OpenBabel e Python
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    openmpi-bin \
    libopenmpi-dev \
    openbabel \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Scarica e installa AutoDock Vina
RUN wget https://github.com/ccsb-scripps/AutoDock-Vina/releases/download/v1.2.5/vina_1.2.5_linux_x86_64 -O /usr/local/bin/vina \
    && chmod +x /usr/local/bin/vina

# Imposta la directory di lavoro
WORKDIR /app

# Copia e installa le dipendenze Python
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# Copia il resto del progetto
COPY . .

# Sovrascriviamo il path di Vina per il container
ENV VINA_EXECUTABLE=/usr/local/bin/vina

# Comando di default: avvia l'orchestratore
CMD ["python3", "run_pipeline.py"]