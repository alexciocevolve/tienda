from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app import services
from app.db import get_db
from app.models import Product

router = APIRouter(prefix="/products", tags=["products"])


def product_to_dict(p: Product) -> dict:
    # This function decides what the API exposes. created_at stays out: the screen does
    # not need it. It is a decision, not a dump of the table.
    return {
        "id": p.id,
        "name": p.name,
        "description": p.description,
        "category": p.category,
        "price_cents": p.price_cents,
        "stock": p.stock,
        "image_url": p.image_url,
    }


@router.get("")
def list_products(
    category: str | None = None,
    limit: int = Query(12, ge=1, le=100),
    cursor: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    products, next_cursor = services.list_products(db, category, cursor, limit)
    return {"items": [product_to_dict(p) for p in products], "next_cursor": next_cursor}


@router.get("/{product_id}")
def get_product(product_id: int, db: Session = Depends(get_db)):
    product = services.get_product(db, product_id)
    if product is None:
        raise HTTPException(404, f"Product {product_id} not found")
    return product_to_dict(product)
