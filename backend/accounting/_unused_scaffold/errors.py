"""統一 error response 格式 + 結構化 log。"""
import json
import logging
import sys
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError


# ============================================================
# 結構化 log(JSON format)
# ============================================================
class JsonFormatter(logging.Formatter):
    def format(self, record):
        payload = {
            "ts":      self.formatTime(record),
            "level":   record.levelname,
            "logger":  record.name,
            "msg":     record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        # 加入 extra fields
        for k, v in record.__dict__.items():
            if k in ("args","asctime","created","exc_info","exc_text","filename","funcName",
                     "levelname","levelno","lineno","message","module","msecs","msg","name",
                     "pathname","process","processName","relativeCreated","stack_info","thread",
                     "threadName","taskName"):
                continue
            try:
                json.dumps(v)
                payload[k] = v
            except Exception:
                pass
        return json.dumps(payload, ensure_ascii=False)


def setup_logging():
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    logging.basicConfig(level=logging.INFO, handlers=[handler])
    # 關掉 uvicorn 雜訊,留 error
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


log = logging.getLogger("chengfu")


# ============================================================
# 統一 error response
# ============================================================
def error_response(code: str, message: str, status: int = 400, hint: str = None, **extra):
    body = {"error": {"code": code, "message": message}}
    if hint:  body["error"]["hint"] = hint
    if extra: body["error"]["extra"] = extra
    return JSONResponse(status_code=status, content=body)


async def http_exception_handler(request: Request, exc: HTTPException):
    log.warning("http_error", extra={
        "path": str(request.url.path),
        "status": exc.status_code,
        "detail": exc.detail,
    })
    return error_response(
        code = f"HTTP_{exc.status_code}",
        message = exc.detail if isinstance(exc.detail, str) else "請求失敗",
        status = exc.status_code,
    )


async def validation_handler(request: Request, exc: RequestValidationError):
    errors = [{"loc": list(e["loc"]), "msg": e["msg"], "type": e["type"]} for e in exc.errors()]
    log.warning("validation_error", extra={"path": str(request.url.path), "errors": errors})
    return error_response(
        code = "VALIDATION_FAILED",
        message = "輸入資料格式錯誤",
        status = 422,
        hint = "請檢查必填欄位與格式",
        errors = errors,
    )


async def general_handler(request: Request, exc: Exception):
    log.error("unhandled_exception", exc_info=exc, extra={"path": str(request.url.path)})
    return error_response(
        code = "INTERNAL_ERROR",
        message = "伺服器內部錯誤 · 已記錄",
        status = 500,
        hint = "請稍後重試,或聯絡管理員並附上上方 ts 時間戳",
    )


def install_error_handlers(app):
    from fastapi.exceptions import HTTPException as FHE
    app.add_exception_handler(FHE, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_handler)
    app.add_exception_handler(Exception, general_handler)
