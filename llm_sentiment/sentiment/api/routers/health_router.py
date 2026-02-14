from fastapi import APIRouter, HTTPException
from llm_sentiment.sentiment.api.core.logging import logger
from clickhouse_driver import Client 
import os
import httpx

router = APIRouter()

# ClickHouse connection settings
CLICKHOUSE_HOST = os.getenv("CLICKHOUSE_HOST", "localhost")
CLICKHOUSE_PORT = int(os.getenv("CLICKHOUSE_PORT", 9000))



def check_api_logic() -> bool:
    try:
        r = httpx.get("http://localhost:8001/health", timeout=2)
        return r.status_code == 200
    except Exception as e:
        logger.error(f"Self HTTP check failed: {e}")
        return False

def check_clickhouse():
    try:
        client = Client(host=CLICKHOUSE_HOST, port=CLICKHOUSE_PORT)
        client.execute("SELECT 1")
        print(f"Connected to {CLICKHOUSE_HOST}:{CLICKHOUSE_PORT}")
        return True
    except Exception as e:
        import traceback
        traceback.print_exc()
        logger.error(f"ClickHouse check failed: host={CLICKHOUSE_HOST}:{CLICKHOUSE_PORT} error={e}")
        return False

def check_pipeline_heartbeat():
    """
    Verify any background worker/pipeline process is alive.
    Replace this stub with real heartbeat logic or file/redis/timestamp check.
    """
    # try:
    #     # Example: look for a heartbeat file updated in last 5 minutes
    #     heartbeat_file = os.getenv("PIPELINE_HEARTBEAT_FILE", "pipeline_heartbeat.txt")
    #     if os.path.exists(heartbeat_file):
    #         import time
    #         last_mod = os.path.getmtime(heartbeat_file)
    #         if time.time() - last_mod < 300:  # 5 minutes
    #             return True
    #     # fallback, could also query Redis or message queue if you track workers there
    #     return False
    # except Exception as e:
    #     logger.error(f"Pipeline heartbeat check failed: {e}")
    #     return False
    return True


@router.get("/health", summary="Simple liveness probe")
def health():
    """
    Lightweight liveness probe — returns immediately with 'ok'
    """
    return {"status": "ok"}


@router.get("/status", summary="System readiness & service status")
def status():
    """
    Readiness/status endpoint used by deployment monitors.
    """
    try:
        db_online = check_clickhouse()
        pipelines_running = check_pipeline_heartbeat()
        api_ok = check_api_logic()
        response = {
            "database": "online" if db_online else "offline",
            "pipelines": "running" if pipelines_running else "stalled",
            "api": "healthy" if api_ok else "unhealthy",
        }

        # set an unhealthy HTTP code when something’s down
        if not db_online or not pipelines_running:
            raise HTTPException(status_code=503, detail=response)

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error computing status: {e}")
        raise HTTPException(status_code=500, detail="Internal status check error")