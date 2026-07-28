# Fly.io（跟其他任何吃 Dockerfile 的平台）用的建置檔。
# 本機不需要 Docker 也能跑（見 README 的三種執行模式）；這支只在部署時用到。
FROM python:3.11-slim

WORKDIR /app

# 先只複製 requirements 再安裝，讓「沒改套件時」能重用建置快取、部署快一點。
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Fly 的 http_service 會把外部流量導到這個內部埠（跟 fly.toml 的 internal_port 對上）。
EXPOSE 8080

# 單一 worker + 多執行緒：這支 App 每個 worker 會把整本和合本讀進記憶體，用多執行緒
# 而不是多 worker，可以只留一份、對 256MB 的小機器比較友善；而且它多半是等 Supabase／
# LINE／AI 回應（I/O 為主），多執行緒剛好夠用。
CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:8080", "--workers", "1", "--threads", "8", "--timeout", "45"]
