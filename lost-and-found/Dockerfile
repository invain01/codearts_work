FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DATABASE_URI=sqlite:////data/app.db \
    UPLOAD_FOLDER=/data/uploads

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    -i https://repo.huaweicloud.com/repository/pypi/simple

COPY app.py config.py models.py ./
COPY services ./services
COPY templates ./templates
COPY static ./static

RUN mkdir -p /data/uploads

EXPOSE 5000
CMD ["waitress-serve", "--listen=0.0.0.0:5000", "app:app"]
