# Agent service: Voice → GPT → WhatsApp → Lovable
FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application code
COPY config.py main.py ./
COPY routers/ routers/
COPY services/ services/

EXPOSE 8000

# Run with env from .env or container env (OPENAI_API_KEY, WHATSAPP_*, etc.)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
