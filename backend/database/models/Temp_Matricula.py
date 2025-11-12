from ..db_base import Base
from sqlalchemy import String, Integer, DateTime, func, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime, timezone

class Temp_Matricula(Base):
    __tablename__ = "Temp_Matricula"

    Periodo: Mapped[str] = mapped_column(String(50), primary_key=True, index=True, nullable=True)
    Sigla: Mapped[str] = mapped_column(String(50), primary_key=True, index=True, nullable=True)
    Nombre_Programa: Mapped[str] = mapped_column(String(100), nullable=True)
    Nombre_Rama: Mapped[str] = mapped_column(String(50), nullable=True)
    Nivel: Mapped[str] = mapped_column(String(50), nullable=True)
    Modalidad: Mapped[str] = mapped_column(String(50), nullable=True)
    Turno: Mapped[str] = mapped_column(String(50), nullable=True)
    Semestre: Mapped[str] = mapped_column(String(50), nullable=True)
    Grupo_Edad: Mapped[str] = mapped_column(String(50), nullable=True)
    Tipo_Ingreso: Mapped[str] = mapped_column(String(50), nullable=True)
    Sexo: Mapped[str] = mapped_column(String(50), nullable=True)
    Matricula: Mapped[int] = mapped_column(nullable=True)
    id_semafoto: Mapped[int] = mapped_column(nullable=True)
    Salones: Mapped[int] = mapped_column(nullable=True)