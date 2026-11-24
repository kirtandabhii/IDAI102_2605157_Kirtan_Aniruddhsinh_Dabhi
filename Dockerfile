FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8501 SHOPIMPACT_DB=/data/shopimpact.db
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN mkdir -p /data
EXPOSE 8501
# The Streamlit app. For the standalone web edition use:  gunicorn web_app:app --bind 0.0.0.0:$PORT
CMD streamlit run app.py --server.port ${PORT} --server.address 0.0.0.0 --server.headless true
