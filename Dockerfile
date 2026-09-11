FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY parser.py .

# Mounted at runtime from the EvoMaster working directory:
#   -v {workDir}/logs:/app/logs
#   -v {workDir}/templates:/app/templates
# Also required at runtime:
#   -v /var/run/docker.sock:/var/run/docker.sock
VOLUME ["/app/logs", "/app/templates"]

# -u disables Python output buffering so responses reach Java immediately.
CMD ["python3", "-u", "parser.py"]
