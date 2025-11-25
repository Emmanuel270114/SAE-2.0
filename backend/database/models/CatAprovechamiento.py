from ast import Tuple
from ..db_base import Base
from sqlalchemy import Integer, Nullable, String, DateTime, false, func, null
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime

class CatAprovechamiento(Base):
    __tablename__ = 'Cat_Aprovechamiento'
    
    Id_Aprovechamiento: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    Aprovechamiento: Mapped[str] = mapped_column(String(100), nullable=False)
    Fecha_Inicio: Mapped[datetime] =mapped_column(DateTime(timezone=True),server_default=func.now(),nullable=false)
    Fecha_Modificacion: Mapped[datetime] =mapped_column(DateTime(timezone=True),server_default=func.now(),nullable=false)
    Fecha_Final: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    Id_Estatus: Mapped[int] = mapped_column(Integer)
    