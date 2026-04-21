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
COPY services/ ./services/

# 健康檢查
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/healthz')"

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
