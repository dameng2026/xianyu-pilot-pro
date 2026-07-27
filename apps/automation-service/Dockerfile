FROM python:3.12-slim-bookworm

WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

COPY requirements.lock ./
RUN pip install --no-cache-dir --require-hashes \
    -i https://pypi.tuna.tsinghua.edu.cn/simple \
    -r requirements.lock
RUN groupadd --gid 10001 app \
    && useradd --uid 10001 --gid app --no-create-home --shell /usr/sbin/nologin app \
    && mkdir -p /app/uploads \
    && chown -R app:app /app
COPY --chown=app:app . .

USER 10001:10001
EXPOSE 12401
CMD ["python", "run-fast.py"]
