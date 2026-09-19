from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app import services
from app.db import get_db
from app.models import Cart, Order, User
from app.routes.cart import current_cart
from app.routes.shared import address_to_dict
from app.routes.users import optional_user

router = APIRouter(prefix="/orders", tags=["orders"])


def order_to_dict(order: Order) -> dict:
    return {
        "id": order.id,
        "customer_email": order.customer_email,
        "status": order.status,
        "total_cents": order.total_cents,
        "created_at": order.created_at.isoformat(),
        # The address as it was when the order was placed. It reads from the related row
        # and still shows the old street after the customer moves, because that row is
        # never edited - moving house writes a new row and retires this one.
        "shipping_address": (
            address_to_dict(order.shipping_address) if order.shipping_address else None
        ),
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
    user: User | None = Depends(optional_user),
    db: Session = Depends(get_db),
):
    # Still no request body. Prices, the total, the buyer and now the shipping address are
    # all decided by the server: the browser says who it is with its token, and the server
    # looks up the address itself. A client allowed to name an address id would be a
    # client able to name somebody else's.
    try:
        order = services.create_order(db, cart, user)
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
