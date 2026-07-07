# SmartRoom backend — dùng chung cho API và worker (command khác nhau)
FROM python:3.12-slim

WORKDIR /app

# libglib2.0-0: runtime cần cho opencv-python-headless
RUN apt-get update \
    && apt-get install -y --no-install-recommends libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
# LƯU Ý: easyocr kéo theo torch (~2GB) — khi tách OCR thành service riêng,
# tạo requirements-core.txt không có easyocr để image API/worker nhẹ hơn nhiều
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY alembic ./alembic
COPY alembic.ini .

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
