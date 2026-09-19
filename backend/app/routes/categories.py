from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import services
from app.db import get_db
from app.models import Category

router = APIRouter(prefix="/categories", tags=["categories"])


def category_to_dict(c: Category) -> dict:
    return {"id": c.id, "name": c.name}


@router.get("")
def list_categories(db: Session = Depends(get_db)):
    # A plain list, with no pagination: there are five of them and the screen shows them
    # all. Pagination is for what grows without limit, and this does not.
    return [category_to_dict(c) for c in services.list_categories(db)]
