from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app import services
from app.db import get_db
from app.models import Cart, Order
from app.routes.cart import current_cart

router = APIRouter(prefix="/orders", tags=["orders"])


def order_to_dict(order: Order) -> dict:
    return {
        "id": order.id,
        "customer_email": order.customer_email,
        "status": order.status,
        "total_cents": order.total_cents,
        "created_at": order.created_at.isoformat(),
        "items": [
            {
                "product_id": item.product_id,
                "name": item.product.name,
                "quantity": item.quantity,
                # The price this was bought at, not the price the product has now.
                "price_cents": item.price_cents,
            }
            for item in order.items
        ],
    }


@router.post("", status_code=201)
def create_order(
    response: Response,
    cart: Cart = Depends(current_cart),
    db: Session = Depends(get_db),
):
    # No request body: there is nothing the client gets to decide. Prices, the total and
    # the buyer all come from the server. For now the buyer is always the same placeholder
    # customer (app/config.py); the next checkpoint takes it from the signed-in user.
    try:
        order = services.create_order(db, cart)
    except ValueError as e:
        # An empty cart or a line short of stock: the request was understood and the rule
        # says no. That is 409, not 400 and not 404.
        raise HTTPException(409, str(e))
    response.headers["Location"] = f"/orders/{order.id}"
    return order_to_dict(order)


@router.get("/{order_id}")
def get_order(order_id: int, db: Session = Depends(get_db)):
    order = services.get_order(db, order_id)
    if order is None:
        raise HTTPException(404, f"Order {order_id} not found")
    return order_to_dict(order)
