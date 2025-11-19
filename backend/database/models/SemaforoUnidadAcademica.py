from ..db_base import Base
from sqlalchemy import Integer, String, DateTime,func
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime

class SemaforoUnidadAcademica(Base):
    __tablename__ = 'Semaforo_Unidad_Academica'

    Id_Periodo: Mapped[int] = mapped_column(Integer, primary_key=True)
    Id_Unidad_Academica: Mapped[int] = mapped_column(Integer, primary_key=True)
    Id_Formato: Mapped[int] = mapped_column(Integer, primary_key=True)
    Id_Semaforo: Mapped[int] = mapped_column(Integer, nullable=False)
    Fecha_Inicio: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(),  nullable=False)
    Fecha_Modificacion: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(),  nullable=False)
    Fecha_Final: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)