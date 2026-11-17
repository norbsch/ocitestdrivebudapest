FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 HOME=/tmp
WORKDIR /opt/app
COPY app/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt && useradd --uid 10001 --create-home workshop
COPY app/app.py app/client.py ./
USER 10001:10001
EXPOSE 8501
CMD ["streamlit", "run", "app.py", "--server.address=0.0.0.0", "--server.port=8501", "--server.headless=true", "--browser.gatherUsageStats=false"]
