FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 HOME=/home/workshop PATH=/opt/venv/bin:$PATH
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates openssl nodejs npm libatomic1 libsndfile1 && rm -rf /var/lib/apt/lists/* \
    && useradd --uid 10001 --create-home workshop \
    && mkdir -p /opt/venv /opt/workshop && chown -R 10001:10001 /opt/venv /opt/workshop
WORKDIR /opt/workshop
USER 10001:10001
COPY --chown=10001:10001 proxy/requirements.txt ./requirements.txt
RUN python -m venv /opt/venv && pip install --no-cache-dir -r requirements.txt \
    && prisma generate --schema="$(python -c 'import importlib.util; from pathlib import Path; print(Path(importlib.util.find_spec("litellm_proxy_extras").origin).parent / "schema.prisma")')"
COPY --chown=10001:10001 runtime/ ./runtime/
EXPOSE 4000
ENTRYPOINT ["python", "/opt/workshop/runtime/start.py"]
CMD ["serve"]
