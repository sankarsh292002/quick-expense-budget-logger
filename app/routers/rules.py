"""
routers/rules.py - the keyword rules behind auto-categorization.

Owner: Member A (API). The matching logic lives in app/categorizer.py (Member D).

    GET    /api/rules          built-in rules + my own rules
    POST   /api/rules          add my own rule, e.g. {"keyword": "bookshop", "category_id": 5}
    DELETE /api/rules/{id}     delete one of my rules (built-in rules: 403)
    POST   /api/categorize     try it: {"description": "REWE Markt Berlin"} -> Food
"""
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from .. import models, schemas
from ..services import CategoryService, RuleService
from ..categorizer import normalize
from ..database import get_db
from ..auth import get_current_user

router = APIRouter(prefix="/api", tags=["auto-categorization"])


def _rule_out(rule: models.CategoryRule) -> dict:
    return {
        "rule_id": rule.rule_id,
        "keyword": rule.keyword,
        "category_id": rule.category_id,
        "category_name": rule.category.name,
        "built_in": rule.user_id is None,
    }


@router.get("/rules", response_model=list[schemas.RuleOut])
def list_rules(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    return [_rule_out(r) for r in RuleService.list_for_user(db, user.user_id)]


@router.post("/rules", response_model=schemas.RuleOut, status_code=status.HTTP_201_CREATED)
def add_rule(data: schemas.RuleCreate, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    keyword = normalize(data.keyword)
    if len(keyword) < 2:
        raise HTTPException(status_code=422, detail="Keyword must contain at least 2 letters or digits")
    if CategoryService.get(db, data.category_id) is None:
        raise HTTPException(status_code=422, detail="Unknown category")
    if RuleService.get_user_rule(db, user.user_id, keyword):
        raise HTTPException(status_code=409, detail=f"You already have a rule for '{keyword}'")
    return _rule_out(RuleService.save_user_rule(db, user.user_id, keyword, data.category_id))


@router.delete("/rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_rule(rule_id: int, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    rule = db.get(models.CategoryRule, rule_id)
    if rule is None or (rule.user_id is not None and rule.user_id != user.user_id):
        raise HTTPException(status_code=404, detail="Rule not found")
    if rule.user_id is None:
        raise HTTPException(status_code=403, detail="Built-in rules cannot be deleted; add your own rule to override it")
    RuleService.delete(db, rule)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/categorize", response_model=schemas.CategorizeOut)
def categorize(data: schemas.CategorizeRequest, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    match = RuleService.build_categorizer(db, user.user_id).categorize(data.description)
    if match:
        category = CategoryService.get(db, match.category_id)
        return {"category_id": category.category_id, "category_name": category.name,
                "matched_keyword": match.keyword, "match_source": match.source}
    other = CategoryService.get_by_name(db, "Other")
    return {"category_id": other.category_id, "category_name": other.name,
            "matched_keyword": None, "match_source": None}
