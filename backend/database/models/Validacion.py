from ..db_base import Base
from sqlalchemy import Integer, String, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime

class Validacion(Base):
    __tablename__ = 'Validacion'

    Id_Periodo: Mapped[int] = mapped_column(Integer, primary_key=True)
    Id_Usuario: Mapped[int] = mapped_column(Integer, primary_key=True)
    Id_Formato: Mapped[int] = mapped_column(Integer, primary_key=True)
    #Tipo de dato de Validado es igual a 'bit' en la base de datos
    Validado: Mapped[bool] = mapped_column(Integer, nullable=False)  # 0=Rechazo, 1=Validación
    Nota: Mapped[str | None] = mapped_column(Text, nullable=True)  # Motivo del rechazo/validación
    Fecha: Mapped[datetime] = mapped_column(DateTime, nullable=False)
