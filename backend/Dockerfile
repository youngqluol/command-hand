FROM python:3.13-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/ \
    PIP_TRUSTED_HOST=mirrors.aliyun.com
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
# 命令手册的离线种子快照：容器构建期无网络，启动时从这里灌入（见 app/command_seed.py）
COPY data ./data
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
