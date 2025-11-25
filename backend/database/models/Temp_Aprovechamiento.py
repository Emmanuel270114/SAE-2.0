
from backend.database.models.CatTipoIngreso import TipoIngreso
from ..db_base import Base
from sqlalchemy import Column, String, Integer, DateTime, func, ForeignKey, null
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime,timezone

class Temp_Aprovechamiento(Base):
    __tablename__ = "Temp_Aprovechamiento"
    
    Periodo: Mapped[str] = mapped_column(String(50), primary_key=True, index=True, nullable=False)
    Sigla: Mapped[str] = mapped_column(String(50), primary_key=True, index=True, nullable=False)
    Nombre_Programa: Mapped[str] = mapped_column(String(100), nullable=True)
    Nombre_Rama: Mapped[str] = mapped_column(String(50), nullable=True)
    Nivel: Mapped[str] = mapped_column(String(50), nullable=True)
    Modalidad: Mapped[str] = mapped_column(String(50), nullable=True)
    Turno: Mapped[str] = mapped_column(String(50), nullable=True)
    Semestre: Mapped[str] = mapped_column(String(50), nullable=True)
    Aprovechamiento: Mapped[str] = mapped_column(String(50), nullable=True)
    Sexo: Mapped[str] = mapped_column(String(50), nullable=True)
    id_semaforo: Mapped[int] = mapped_column(nullable=True)
    Alumnos: Mapped[int] =mapped_column(nullable=True)