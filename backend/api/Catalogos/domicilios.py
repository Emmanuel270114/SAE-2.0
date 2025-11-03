from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy import text

from backend.database.connection import get_db
from backend.core.templates import templates

router = APIRouter()


@router.get("/domicilios", response_class=HTMLResponse)
def domicilios_view(
    request: Request,
    UUsuario: str = "paco",
    HHost: str = "Test",
    PPeriodo: str = "2025-2026/1",
    db: Session = Depends(get_db)
):
    """
    Vista para consultar los domicilios mediante un Stored Procedure.
    """

    try:
        # Ejecutar el Stored Procedure con parámetros nombrados
        query = text("""
            EXEC dbo.SP_Consulta_Catalogo_Unidad_Academica
                @UUsuario = :UUsuario,
                @HHost = :HHost,
                @PPeriodo = :PPeriodo
        """)
        resultado = db.execute(query, {
            "UUsuario": UUsuario,
            "HHost": HHost,
            "PPeriodo": PPeriodo
        })

        # Convertir el resultado a lista de diccionarios
        data = [dict(row) for row in resultado.mappings().all()]
        print(data)

    except Exception as e:
        print("Error al ejecutar SP_Consulta_Catalogo_Unidad_Academica:", e)
        data = []

    # Renderizar la plantilla HTML con los resultados
    return templates.TemplateResponse(
        "catalogos/domicilios.html",
        {
            "request": request,
            "domicilios": data
        }
    )
