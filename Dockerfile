FROM python:3.12-slim

WORKDIR /app

# Системные зависимости (для сборки natasha/numpy)
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc && \
    rm -rf /var/lib/apt/lists/*

# Зависимости Python (кэшируем слой)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем код
COPY . .

EXPOSE 8000

# Запуск с 4 воркерами для параллельной обработки NER
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
