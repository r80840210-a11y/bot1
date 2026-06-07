FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Открываем порт 8080 для Flask
EXPOSE 8080

CMD ["python", "bot.py"]
