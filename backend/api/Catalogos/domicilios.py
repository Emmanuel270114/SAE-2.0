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
        #print(data)
        Rama = consultaRama(db)
        print(Rama)
        Entidad = consultaEntidad(db)
        #print(Entidad)

    except Exception as e:
        print("Error al ejecutar SP_Consulta_Catalogo_Unidad_Academica:", e)
        data = []

    # Renderizar la plantilla HTML con los resultados
    return templates.TemplateResponse(
        "catalogos/domicilios.html",
        {
            "request": request,
            "domicilios": data,
            "rol": Rol,
            "rama": Rama,
            "entidad": Entidad
        }
    )


def consultaRama(db: Session):
    try:
        #Ejecutamos el SP
        query = text("""EXEC dbo.SP_Consulta_Catalogo_Rama""")
        resultado = db.execute(query, )
        # Convertir el resultado a lista de diccionarios
        data = [dict(row) for row in resultado.mappings().all()]
        return data  
    except Exception as e:
        return {"error": str(e)}
    
def consultaEntidad(db: Session):
    try:
        #Ejecutamos el SP
        query = text("""EXEC dbo.SP_Consulta_Catalogo_Entidad""")
        resultado = db.execute(query, )
        # Convertir el resultado a lista de diccionarios
        data = [dict(row) for row in resultado.mappings().all()]
        return data  
    except Exception as e:
        return {"error": str(e)}
    
    @router.post("/registrarUA")
def registrar_ua(data: UARequest, db: Session = Depends(get_db)):
    print("Registrar")

@router.put("/actualizarUA/{sigla}")
def actualizar_ua(sigla: str, data: UARequest, db: Session = Depends(get_db)):
    print("actualizar")

@router.delete("/eliminarUA/{sigla}")
def eliminar_ua(sigla: str, db: Session = Depends(get_db)):
    print("Eliminar")
