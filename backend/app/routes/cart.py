from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from app import services
from app.db import get_db
from app.models import Cart
from app.routes.shared import absolute_url
from app.schemas import QuantityIn

router = APIRouter(prefix="/cart", tags=["cart"])


def current_cart(
    request: Request,
    x_cart_token: str = Header(),
    db: Session = Depends(get_db),
) -> Cart:
    # The token travels in a header, not in the path: a cart address that appears in the
    # browser bar ends up copied into a chat, and then it is someone else's cart.
    cart = services.get_cart(db, x_cart_token)
    if cart is None:
        raise HTTPException(404, "Cart not found")
    return cart


def cart_to_dict(cart: Cart, request: Request) -> dict:
    return {
        "token": cart.token,
        "items": [
            {
                "product_id": item.product_id,
                "name": item.product.name,
                "image_url": absolute_url(request, item.product.image_url),
                # Today's price and the line total, both worked out on the server.
                "price_cents": item.product.price_cents,
                "quantity": item.quantity,
                "subtotal_cents": item.product.price_cents * item.quantity,
            }
            for item in cart.items
        ],
        "total_cents": services.cart_total_cents(cart),
    }


@router.post("", status_code=201)
def create_cart(request: Request, db: Session = Depends(get_db)):
    # 201 and not 200: this call CREATES something. The token in the answer is what the
    # browser has to keep and send back in the header from now on.
    return cart_to_dict(services.create_cart(db), request)


@router.get("")
def get_cart(request: Request, cart: Cart = Depends(current_cart)):
    return cart_to_dict(cart, request)


@router.put("/items/{product_id}")
def set_cart_item(
    product_id: int,
    body: QuantityIn,
    request: Request,
    cart: Cart = Depends(current_cart),
    db: Session = Depends(get_db),
):
    # PUT, not POST: it SETS the quantity to a value rather than adding to it. Sending it
    # twice leaves the same cart, so a retry after a dropped connection is harmless.
    try:
        updated = services.set_cart_item(db, cart, product_id, body.quantity)
    except ValueError as e:
        raise HTTPException(409, str(e))  # the rule broken is stock, not a missing thing
    if updated is None:
        raise HTTPException(404, f"Product {product_id} not found")
    return cart_to_dict(updated, request)


@router.delete("/items/{product_id}")
def remove_cart_item(
    product_id: int,
    request: Request,
    cart: Cart = Depends(current_cart),
    db: Session = Depends(get_db),
):
    if not services.remove_cart_item(db, cart, product_id):
        raise HTTPException(404, f"Product {product_id} is not in the cart")
    return cart_to_dict(services.get_cart(db, cart.token), request)
