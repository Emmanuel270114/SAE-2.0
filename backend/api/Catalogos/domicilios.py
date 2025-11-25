from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy import text

from backend.database.connection import get_db
from backend.core.templates import templates

router = APIRouter()


PPeriodo: str = "2025-2026/1"
HHost: str = "Test"


@router.get("/domicilios", response_class=HTMLResponse)
def domicilios_view(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Vista para consultar los domicilios mediante un Stored Procedure.
    """
    UUsuario = getUsuario(request)
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
        #print(Rama)
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
def registrar_ua(data: dict, request: Request, db: Session = Depends(get_db)):
    print("Datos recibidos en REGISTRAR:")
    print(data)  # <-- imprime todo el JSON recibido
    try:
        UUsuario = getUsuario(request)
        query = text("""
            EXEC [dbo].[SP_Alta_Catalogo_Unidad_Academica]
                @UUnidad_Academica = :unidad_academica,
                @NNombre = :nombre,
                @CClave = :clave,
                @DDirector = :director,
                @IImagen = NULL,
                @RRama = :rama,
                @EEntidad = :entidad,
                @MMunicipio = :municipio,
                @CCalle = :calle,
                @NNumero = :numero,
                @CColonia = :colonia,
                @CCP = :cp,
                @UUsuario = :usuario,
                @HHost = :host,
                @PPeriodo = :periodo
        """)
        db.execute(query, {
            "unidad_academica": data.get("sigla"),
            "nombre": data.get("nombre"),
            "clave": data.get("clave"),
            "director": data.get("director"),
            "rama": data.get("rama"),
            "entidad": data.get("entidad"),
            "municipio": data.get("municipio"),
            "calle": data.get("calle"),
            "numero":  int(data.get("numero")) if data.get("numero") else "SN",
            "colonia": data.get("colonia"),
            "cp": data.get("cp"),
            "usuario": UUsuario,
            "host": HHost, 
            "periodo": PPeriodo
        })
        db.commit()
        
        print("UA registrada correctamente")
    except Exception as e:
        db.rollback()
        print("Error al registrar UA:", e)
        return {"status": "error", "msg": "Error al registrar UA"}


    return {"status": "ok", "msg": "UA registrada correctamente"}


@router.put("/actualizarUA/")
def actualizar_ua(data: dict, request: Request, db: Session = Depends(get_db)):

    print("\nDatos recibidos en ACTUALIZAR:")
    print("Body recibido:", data)
    try:
        UUsuario = getUsuario(request)
        query = text("""
            EXEC [dbo].[SP_Modifica_Catalogo_Unidad_Academica]
                @UUnidad_Academica = :unidad_academica,
                @NNombre = :nombre,
                @CClave = :clave,
                @DDirector = :director,
                @IImagen = NULL,
                @RRama = :rama,
                @UUsuario = :usuario,
                @HHost = :host,
                @PPeriodo = :periodo
        """)
        db.execute(query, {
            "unidad_academica": data.get("sigla"),
            "nombre": data.get("nombre"),
            "clave": data.get("clave"),
            "director": data.get("director"),
            "rama": data.get("rama"),
            "usuario": UUsuario,
            "host": HHost,
            "periodo": PPeriodo
        })


        db.commit()
        print("UA actualizada correctamente")
    except Exception as e:
        db.rollback()
        print("Error al actualizar UA:", e)
        return {"status": "error", "msg": "Error al actualizar UA"}
    

    return {"status": "ok",  "msg": "UA actualizada correctamente"}




@router.delete("/eliminarUA/{sigla}")
def eliminar_ua(sigla: str, request: Request, db: Session = Depends(get_db)):
    print("\nDatos recibidos en ELIMINAR:")
    print("Sigla:", sigla)

    
    try:
        UUsuario = getUsuario(request)
        query = text("""
            EXEC [dbo].[SP_Baja_Catalogo_Unidad_Academica]
                @UUnidad_Academica = :unidad_academica,
                @UUsuario = :usuario,
                @HHost = :host  ,
                @PPeriodo = :periodo
        """)    
            
        db.execute(query, {
                "unidad_academica": sigla,
                "usuario": UUsuario,
                "host": HHost,
                "periodo": PPeriodo
            }
        )
        db.commit()
        print("UA eliminada correctamente")
    except Exception as e:
        db.rollback()
        print("Error al eliminar UA:", e)
        return {"status": "error", "msg": str(e)}

    return {"status": "ok", "msg": "UA eliminada correctamente"}


def getUsuario(request: Request):
    UUsuario = request.cookies.get("nombre_usuario", "")
    return UUsuario 