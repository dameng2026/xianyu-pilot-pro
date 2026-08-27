FROM python:3.12-slim-bookworm

WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

COPY requirements.lock ./
RUN pip install --no-cache-dir --require-hashes -r requirements.lock \
    -i https://pypi.tuna.tsinghua.edu.cn/simple
# 2026-08-02 添加 redis 包（x5sec_cache_client.py 需要，用于从 Redis 读取缓存的 x5sec）
# 单独安装以避免重新生成整个 lock 文件
RUN pip install --no-cache-dir \
    -i https://pypi.tuna.tsinghua.edu.cn/simple \
    redis==5.0.8
RUN groupadd --gid 10001 app \
    && useradd --uid 10001 --gid app --no-create-home --shell /usr/sbin/nologin app \
    && mkdir -p /app/uploads \
    && chown -R app:app /app
COPY --chown=app:app . .

USER 10001:10001
EXPOSE 12401
CMD ["python", "run-fast.py"]
