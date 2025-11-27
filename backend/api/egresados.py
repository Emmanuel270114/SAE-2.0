from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy import text

from backend.database.connection import get_db
from backend.core.templates import templates

router = APIRouter()


@router.get("/egresados", response_class=HTMLResponse)
def egresados_view(
    request: Request,
    HHost: str = "Test",
    PPeriodo: str = "2025-2026/1",
    db: Session = Depends(get_db)
):
    """
    Vista para consultar los egresados mediante un Stored Procedure.
    """
    UUsuario = str(request.cookies.get("nombre_usuario", ""))
    Rol = str(request.cookies.get("nombre_rol",""))    
    try:
        # Ejecutar el Stored Procedure con parámetros nombrados
        query = text("""
            EXEC dbo.SP_Consulta_Catalogo_Egresados
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
        print("Error al ejecutar SP_Consulta_Catalogo_Egresados:", e)
        data = []

    # Renderizar la plantilla HTML con los resultados
    return templates.TemplateResponse(
        "egresados.html",
        {
            "request": request,
            "egresados": data,
            "rol": Rol
        }
    )

