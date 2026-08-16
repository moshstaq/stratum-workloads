import os
import time
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

app = FastAPI(
    title="Stratum Catalogue Service",
    description="Product catalogue for Stratum Retail Group flash sales",
    version="1.0.0",
)

# In-memory product catalogue — replaced by database in production
PRODUCTS = {
    "flash-001": {
        "id": "flash-001",
        "name": "Wireless Headphones Pro",
        "price": 49.99,
        "stock": 500,
        "flash_sale": True,
        "discount_pct": 40,
    },
    "flash-002": {
        "id": "flash-002",
        "name": "Smart Watch Elite",
        "price": 89.99,
        "stock": 300,
        "flash_sale": True,
        "discount_pct": 35,
    },
    "flash-003": {
        "id": "flash-003",
        "name": "Portable Speaker Max",
        "price": 34.99,
        "stock": 1000,
        "flash_sale": True,
        "discount_pct": 50,
    },
    "reg-001": {
        "id": "reg-001",
        "name": "USB-C Cable 2m",
        "price": 9.99,
        "stock": 5000,
        "flash_sale": False,
        "discount_pct": 0,
    },
    "reg-002": {
        "id": "reg-002",
        "name": "Phone Case Standard",
        "price": 14.99,
        "stock": 3000,
        "flash_sale": False,
        "discount_pct": 0,
    },
}

REQUEST_COUNT = {"total": 0, "start_time": time.time()}


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": "catalogue",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/")
async def root():
    return {
        "service": "stratum-catalogue",
        "version": "1.0.0",
        "region": os.getenv("AWS_REGION", os.getenv("AZURE_REGION", "unknown")),
        "message": "Stratum Retail Group — Catalogue Service",
    }


@app.get("/products")
async def list_products():
    REQUEST_COUNT["total"] += 1
    return {
        "products": list(PRODUCTS.values()),
        "count": len(PRODUCTS),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/products/{product_id}")
async def get_product(product_id: str):
    REQUEST_COUNT["total"] += 1
    product = PRODUCTS.get(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    result = {**product}
    if result["flash_sale"]:
        result["sale_price"] = round(
            result["price"] * (1 - result["discount_pct"] / 100), 2
        )

    return result


@app.get("/flash-sale")
async def flash_sale_products():
    REQUEST_COUNT["total"] += 1
    flash_items = [
        {
            **p,
            "sale_price": round(p["price"] * (1 - p["discount_pct"] / 100), 2),
        }
        for p in PRODUCTS.values()
        if p["flash_sale"]
    ]
    return {
        "flash_sale_active": len(flash_items) > 0,
        "products": flash_items,
        "count": len(flash_items),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/metrics")
async def metrics():
    elapsed = time.time() - REQUEST_COUNT["start_time"]
    rps = REQUEST_COUNT["total"] / elapsed if elapsed > 0 else 0
    return {
        "total_requests": REQUEST_COUNT["total"],
        "uptime_seconds": round(elapsed, 2),
        "requests_per_second": round(rps, 4),
    }