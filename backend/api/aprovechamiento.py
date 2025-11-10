from fastapi import APIRouter, Request, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
import json
from typing import List, Dict, Any
from fastapi import HTTPException
from datetime import datetime

from backend.core.templates import templates
from backend.database.connection import get_db




router = APIRouter()

@router.get("/aprovechamiento")
async def aprovechamiento_sp_view(request: Request, db: Session = Depends(get_db)):
    
    #Otener datos del ususario logueado desde las cookies
    
    id_unidad_academica = int(request.cookies.get("id_unidad_academica", 0))