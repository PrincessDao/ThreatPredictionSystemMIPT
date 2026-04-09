from fastapi import Request
import time
import json
import logging

logger = logging.getLogger("uvicorn.access")

async def log_requests(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    process_time = time.time() - start
    log_dict = {
        "method": request.method,
        "url": str(request.url),
        "status_code": response.status_code,
        "process_time": round(process_time, 4),
    }
    logger.info(json.dumps(log_dict))
    return response
