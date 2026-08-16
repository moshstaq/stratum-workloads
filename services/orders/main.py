import os
import json
import uuid
import time
from datetime import datetime, timezone
from typing import Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(
    title="Stratum Orders Service",
    description="Order processing for Stratum Retail Group flash sales",
    version="1.0.0",
)

# In-memory order store — replaced by database in production
ORDERS = {}
REQUEST_COUNT = {"total": 0, "start_time": time.time()}


class OrderItem(BaseModel):
    product_id: str
    quantity: int
    unit_price: float


class OrderRequest(BaseModel):
    customer_id: str
    items: list[OrderItem]
    flash_sale: Optional[bool] = False


class Order(BaseModel):
    order_id: str
    customer_id: str
    items: list[OrderItem]
    total: float
    flash_sale: bool
    status: str
    created_at: str
    region: str


def get_secret_client():
    """Retrieve config from Secrets Manager via IRSA/workload identity."""
    try:
        import boto3

        region = os.getenv("AWS_REGION", "us-east-1")
        client = boto3.client("secretsmanager", region_name=region)
        secret_name = os.getenv("SECRET_NAME", "stratum/platform/app-config")
        response = client.get_secret_value(SecretId=secret_name)
        return json.loads(response["SecretString"])
    except Exception as e:
        return {"error": str(e), "source": "fallback"}


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": "orders",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/")
async def root():
    return {
        "service": "stratum-orders",
        "version": "1.0.0",
        "region": os.getenv("AWS_REGION", os.getenv("AZURE_REGION", "unknown")),
        "message": "Stratum Retail Group — Orders Service",
    }


@app.post("/orders")
async def create_order(request: OrderRequest):
    REQUEST_COUNT["total"] += 1

    order_id = str(uuid.uuid4())[:8]
    total = sum(item.unit_price * item.quantity for item in request.items)

    if request.flash_sale:
        total = round(total * 0.85, 2)

    order = Order(
        order_id=order_id,
        customer_id=request.customer_id,
        items=request.items,
        total=total,
        flash_sale=request.flash_sale,
        status="confirmed",
        created_at=datetime.now(timezone.utc).isoformat(),
        region=os.getenv("AWS_REGION", os.getenv("AZURE_REGION", "unknown")),
    )

    ORDERS[order_id] = order.model_dump()
    return order


@app.get("/orders/{order_id}")
async def get_order(order_id: str):
    REQUEST_COUNT["total"] += 1
    order = ORDERS.get(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


@app.get("/orders")
async def list_orders():
    REQUEST_COUNT["total"] += 1
    return {
        "orders": list(ORDERS.values()),
        "count": len(ORDERS),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/config")
async def config():
    """Validates IRSA/workload identity by retrieving platform secrets."""
    config_data = get_secret_client()
    return {
        "status": "success" if "error" not in config_data else "fallback",
        "config": config_data,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/metrics")
async def metrics():
    elapsed = time.time() - REQUEST_COUNT["start_time"]
    rps = REQUEST_COUNT["total"] / elapsed if elapsed > 0 else 0
    return {
        "total_requests": REQUEST_COUNT["total"],
        "total_orders": len(ORDERS),
        "uptime_seconds": round(elapsed, 2),
        "requests_per_second": round(rps, 4),
    }