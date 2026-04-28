# 承富會計 API · FastAPI + PyMongo
FROM python:3.12-slim@sha256:804ddf3251a60bbf9c92e73b7566c40428d54d0e79d3428194edf40da6521286

WORKDIR /app

# Round 9 implicit · OCR 系統依賴(承富政府 PDF 高比例掃描 · 老闆 Q1)
# tesseract-ocr-chi-tra · 繁中 · ~50MB · 沒裝 PDF OCR fallback 會 silent skip
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-chi-tra \
    tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*

# Codex Round 10.5 · PyMuPDF textpage_ocr 需要 TESSDATA_PREFIX 指向 tessdata 目錄
# Debian apt 裝的 tesseract 5.x 路徑在 /usr/share/tesseract-ocr/5/tessdata/
# 沒設會失敗 · 且錯誤只在 OCR probe 才看得到
ENV TESSDATA_PREFIX=/usr/share/tesseract-ocr/5/tessdata/

# 安裝依賴
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 應用
COPY main.py .
COPY auth_deps.py .
COPY config.py .
COPY orchestrator.py .
COPY infra/ ./infra/
COPY services/ ./services/
COPY routers/ ./routers/

# 健康檢查
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/healthz')"

EXPOSE 8000

# v1.66 O6 · workers 2 → 4 · 並發 ×2 · 大 PDF 上傳不阻塞其他 user
# Mac mini M4 24GB 跑 4 worker 約 800MB · 寬裕
# 注意:多 worker 時 slowapi memory:// + module-level cache 會分散
#       _AGENT_FORBIDDEN_CACHE 每個 worker 自己 cache · 5min TTL 仍合理
#       OCR _OCR_AVAILABLE 每個 worker 各 probe 一次 · OK
#       slowapi 限速「per worker」放鬆為 4x · 接受(30 人前再升 Redis)
# 若要嚴格 cross-worker 限速 · v2.0 改 Redis backend
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
