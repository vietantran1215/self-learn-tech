FROM python:3.12-slim
WORKDIR /app
COPY backend/pyproject.toml backend/requirements.lock.txt ./
RUN pip install --no-cache-dir -r requirements.lock.txt
COPY backend/app app
RUN pip install --no-cache-dir --no-deps .
COPY evaluation evaluation
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
