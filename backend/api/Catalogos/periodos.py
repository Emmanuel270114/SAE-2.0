from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy import text

from backend.database.connection import get_db
from backend.core.templates import templates

router = APIRouter()

HHost: str = "Test"
PPeriodo: str = "2025-2026/1"

@router.get("/periodos", response_class=HTMLResponse)
def domicilios_view(
    request: Request,
    db: Session = Depends(get_db)
):
    
    UUsuario = str(request.cookies.get("nombre_usuario", ""))
    Rol = str(request.cookies.get("nombre_rol",""))




    try:
        # Ejecutar el Stored Procedure con parámetros nombrados
        query = text("""
            EXEC dbo.SP_Consulta_Catalogo_Periodos
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
        print("Error al ejecutar SP_Consulta_Catalogo_Periodos:", e)
        data = []

    # Renderizar la plantilla HTML con los resultados
    return templates.TemplateResponse(
        "catalogos/periodos.html",
        {
            "request": request,
            "periodos": data,
            "rol": Rol
        }
    )

@router.post("/nuevo_periodo")  
def nuevo_periodo(data: dict, db: Session = Depends(get_db)):
    print(data)
    try:
        query = text("""
            EXEC dbo.SP_Iniciar_Periodo
                @PPeriodo = :PPeriodo,
                @HHost = :HHost,
                @UUsuario = :UUsuario
                
        """)
        resultado = db.execute(query, {
            "PPeriodo": data["periodo"],
            "HHost": HHost,
            "UUsuario": UUsuario
        })

        # Convertir el resultado a lista de diccionarios
        data = [dict(row) for row in resultado.mappings().all()]
        print(data) 
    except Exception as e:
        print("Error al ejecutar SP_Iniciar_Periodo:", e)
        return {"success": False}
    return {"success": True}