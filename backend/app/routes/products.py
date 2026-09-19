from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app import services
from app.db import get_db
from app.models import Product, ProductPriceHistory
from app.routes.shared import absolute_url

router = APIRouter(prefix="/products", tags=["products"])


def product_to_dict(p: Product, request: Request) -> dict:
    # This function decides what the API exposes. created_at stays out: the screen does
    # not need it. It is a decision, not a dump of the table.
    return {
        "id": p.id,
        "name": p.name,
        "description": p.description,
        # The table changed, this answer does not: the API promised a name and still sends
        # one, read now from the related row. Nothing outside the server has to be rewritten.
        "category": p.category.name,
        "price_cents": p.price_cents,
        "stock": p.stock,
        # How to get the image: a plain GET to this address (see absolute_url).
        "image_url": absolute_url(request, p.image_url),
    }


@router.get("")
def list_products(
    request: Request,
    category: str | None = None,
    limit: int = Query(12, ge=1, le=100),
    cursor: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    products, next_cursor = services.list_products(db, category, cursor, limit)
    return {"items": [product_to_dict(p, request) for p in products], "next_cursor": next_cursor}


@router.get("/{product_id}")
def get_product(product_id: int, request: Request, db: Session = Depends(get_db)):
    product = services.get_product(db, product_id)
    if product is None:
        raise HTTPException(404, f"Product {product_id} not found")
    return product_to_dict(product, request)


def price_change_to_dict(change: ProductPriceHistory) -> dict:
    # No product_id: the caller asked for one product's history and already knows which.
    return {
        "changed_at": change.changed_at,
        "previous_price_cents": change.previous_price_cents,
        "price_cents": change.price_cents,
    }


@router.get("/{product_id}/price-history")
def get_price_history(product_id: int, db: Session = Depends(get_db)):
    history = services.list_price_history(db, product_id)

    # The two answers this endpoint can give, and why they are different:
    #
    #   404      - there is no such product. The address names nothing.
    #   200 []   - the product is there and its price has never changed. That is a true,
    #              complete answer, and an empty collection is not a missing resource.
    #
    # Note that this shop makes the OPPOSITE choice on purpose elsewhere: somebody else's
    # order answers 404 rather than 403, exactly so that a caller CANNOT tell "not yours"
    # from "does not exist". Both come from the same rule - choosing a status code is
    # deciding what the caller is allowed to distinguish - and here we want them to.
    if history is None:
        raise HTTPException(404, f"Product {product_id} not found")

    return [price_change_to_dict(change) for change in history]
