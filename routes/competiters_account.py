from fastapi import APIRouter, HTTPException, Depends
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel
from db.db import get_connection
from sqlalchemy.orm import Session

router = APIRouter()

class CompetiterAccountBase(BaseModel):
    role_models: str
    industry_standard: str
    competition: str
    persona_id: int

class CompetiterAccountCreate(CompetiterAccountBase):
    pass

class CompetiterAccount(CompetiterAccountBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

@router.post("/", response_model=CompetiterAccount)
def create_competiter_account(account: CompetiterAccountCreate, db: Session = Depends(get_connection)):
    db_account = CompetiterAccount(**account.dict())
    db.add(db_account)
    db.commit()
    db.refresh(db_account)
    return db_account

@router.get("/", response_model=List[CompetiterAccount])
def get_all_competiter_accounts(skip: int = 0, limit: int = 100, db: Session = Depends(get_connection)):
    accounts = db.query(CompetiterAccount).offset(skip).limit(limit).all()
    return accounts

@router.get("/{account_id}", response_model=CompetiterAccount)
def get_competiter_account(account_id: int, db: Session = Depends(get_connection)):
    account = db.query(CompetiterAccount).filter(CompetiterAccount.id == account_id).first()
    if account is None:
        raise HTTPException(status_code=404, detail="Competiter account not found")
    return account

@router.put("/{account_id}", response_model=CompetiterAccount)
def update_competiter_account(account_id: int, account: CompetiterAccountCreate, db: Session = Depends(get_connection)):
    db_account = db.query(CompetiterAccount).filter(CompetiterAccount.id == account_id).first()
    if db_account is None:
        raise HTTPException(status_code=404, detail="Competiter account not found")
    
    for key, value in account.dict().items():
        setattr(db_account, key, value)
    
    db.commit()
    db.refresh(db_account)
    return db_account

@router.delete("/{account_id}")
def delete_competiter_account(account_id: int, db: Session = Depends(get_connection)):
    db_account = db.query(CompetiterAccount).filter(CompetiterAccount.id == account_id).first()
    if db_account is None:
        raise HTTPException(status_code=404, detail="Competiter account not found")
    
    db.delete(db_account)
    db.commit()
    return {"message": "Competiter account deleted successfully"}
