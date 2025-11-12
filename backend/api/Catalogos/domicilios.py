from warnings import catch_warnings
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
    HHost: str = "Test",
    PPeriodo: str = "2025-2026/1",
    db: Session = Depends(get_db)
):
    """
    Vista para consultar los domicilios mediante un Stored Procedure.
    """
    UUsuario = request.cookies.get("nombre_usuario", "")
    Rol = str(request.cookies.get("nombre_rol",""))

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
        consultaRama()

    except Exception as e:
        print("Error al ejecutar SP_Consulta_Catalogo_Unidad_Academica:", e)
        data = []

    # Renderizar la plantilla HTML con los resultados
    return templates.TemplateResponse(
        "catalogos/domicilios.html",
        {
            "request": request,
            "domicilios": data,
            "rol": Rol
        }
    )


def consultaRama():
    try:
        query = text("SELECT * FROM cat_rama")  # 👈 envolver en text()
        resultado = db.execute(query)
        datos = resultado.fetchall()
        return {"ramas": [dict(row._mapping) for row in datos]}  # _mapping para SQLAlchemy 2.x
    except Exception as e:
        return {"error": str(e)}
    