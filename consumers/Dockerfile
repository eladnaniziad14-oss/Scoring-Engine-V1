# ===============================
# Base image
# ===============================
FROM python:3.11-slim

# ===============================
# Copie des fichiers et installation
# ===============================
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

# ===============================
# Variable d'environnement pour choisir le consumer
# Exemple : L1 ou L2
# ===============================
ENV PYTHONPATH=/app
ENV CONSUMER_TYPE=L1

# ===============================
# CMD générique
# ===============================
CMD ["sh", "-c", "python $CONSUMER_TYPE/run.py"]
