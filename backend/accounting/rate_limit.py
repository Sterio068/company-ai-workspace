"""Rate limiting per endpoint · 避免 abuse。

用法:
  from rate_limit import limiter

  @router.post("/classify")
  @limiter.limit("10/minute")
  def classify(request: Request, ...): ...

安裝:
  pip install slowapi
"""
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded


limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["300/minute"],  # 每 IP 全系統預設
)


def install_rate_limit(app):
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# 各 endpoint 建議 limit(供 route 套用)
LIMITS = {
    "safety_classify":  "10/minute",   # L3 classifier 重 · 限流
    "orchestrator":     "5/minute",    # 多 Agent 呼叫貴
    "export":           "2/hour",      # 匯出全部資料
    "email_send":       "20/hour",     # 防 Email 濫發
    "default":          "60/minute",   # 一般 CRUD
}
