from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app import services
from app.db import get_db
from app.models import User
from app.routes.shared import address_to_dict
from app.schemas import AddressIn, LoginIn, UserIn

router = APIRouter(tags=["users"])


def _bearer_token(authorization: str | None) -> str:
    # "Authorization: Bearer <token>". Anything else is not a sign-in attempt we can read.
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Invalid or expired token")
    return authorization.removeprefix("Bearer ")


def current_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    # A missing header is answered with 401 and not with the 422 that a required header
    # would give: "you are not signed in" is the honest answer, not "your request is
    # malformed". The message is the same whether the token is unknown or simply old,
    # because the difference is of no use to the person asking.
    user = services.get_user_by_session(db, _bearer_token(authorization))
    if user is None:
        raise HTTPException(401, "Invalid or expired token")
    return user


def optional_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User | None:
    """The signed-in user, or None for somebody buying without an account.

    No header at all means a guest, which is allowed. A header that IS there and does not
    work is a different thing: somebody tried to say who they were and failed, and
    quietly serving them as a guest would hide an expired session instead of showing it.
    """
    if authorization is None:
        return None
    return current_user(authorization, db)


def user_to_dict(user: User) -> dict:
    # password_hash is not here, and it never will be. It is not needed on any screen, and
    # what is never sent cannot leak through a screenshot, a log or a cached response.
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "created_at": user.created_at.isoformat(),
    }


@router.post("/users", status_code=201)
def register(body: UserIn, db: Session = Depends(get_db)):
    user = services.register_user(db, body.email, body.password, body.full_name)
    if user is None:
        raise HTTPException(409, f"Email {body.email} is already registered")
    return user_to_dict(user)


@router.post("/login")
def login(body: LoginIn, db: Session = Depends(get_db)):
    session = services.login(db, body.email, body.password)
    if session is None:
        # Deliberately the same sentence whether the email is unknown or the password is
        # wrong. Saying "no account with that email" turns the login form into a way of
        # finding out who is registered here.
        raise HTTPException(401, "Invalid email or password")
    return {"token": session.token}


@router.post("/logout", status_code=204)
def logout(authorization: str | None = Header(default=None), db: Session = Depends(get_db)):
    services.logout(db, _bearer_token(authorization))


@router.get("/me")
def me(user: User = Depends(current_user)):
    return user_to_dict(user)


@router.get("/me/addresses")
def list_addresses(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return [address_to_dict(a) for a in services.list_addresses(db, user)]


@router.put("/me/addresses/{kind}")
def save_address(
    # Literal, so FastAPI itself refuses anything that is not one of the two kinds and
    # answers 422 before our code runs. No hand-written check, and it shows up in /docs.
    kind: Literal["shipping", "billing"],
    body: AddressIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    # PUT and not POST: it sets what the address at this slot IS. Sending it twice leaves
    # the same address, and the caller does not have to know whether one existed already.
    address = services.save_address(db, user, kind == "billing", body)
    return address_to_dict(address)


@router.delete("/me/addresses/{kind}", status_code=204)
def delete_address(
    kind: Literal["shipping", "billing"],
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    # The row is not removed, only retired: an order may point at it, and the foreign key
    # is there to stop that order losing the address it was actually sent to.
    if not services.deactivate_address(db, user, kind == "billing"):
        raise HTTPException(404, f"No {kind} address to delete")
