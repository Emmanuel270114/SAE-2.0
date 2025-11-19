# routers/login.py
from backend.database.connection import get_db
from backend.services.usuario_service import validacion_usuario
from backend.schemas.Usuario import UsuarioLogin, UsuarioResponse
from backend.core.templates import templates, static

from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from sqlalchemy.orm import Session

from typing import Optional

router = APIRouter()

@router.get("/", response_class=HTMLResponse)
async def login_view(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@router.post("/", response_class=HTMLResponse)
async def login(
    request: Request,
    usuario_email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    exito = False
    mensaje = ""
    try:
        if validacion_usuario(db, usuario_email, password):
            exito = True
            from backend.crud.Usuario import read_user_by_email, read_user_by_username
            from backend.database.models.CatRoles import CatRoles
            from backend.database.models.CatNivel import CatNivel
            from backend.database.models.CatUnidadAcademica import CatUnidadAcademica
            
            user = read_user_by_email(db, usuario_email)
            if user is None:
                user = read_user_by_username(db, usuario_email)

            id_unidad = user.Id_Unidad_Academica if user else 1
            id_rol = user.Id_Rol if user else 2
            id_nivel = user.Id_Nivel if user else 1
            id_usuario = user.Id_Usuario if user else None
            
            # Obtener nombres del rol, nivel y sigla de la unidad académica
            rol = db.query(CatRoles).filter(CatRoles.Id_Rol == id_rol).first()
            nivel = db.query(CatNivel).filter(CatNivel.Id_Nivel == id_nivel).first()
            unidad = db.query(CatUnidadAcademica).filter(CatUnidadAcademica.Id_Unidad_Academica == id_unidad).first()
            
            nombre_rol = rol.Rol if rol else "Usuario"
            nombre_nivel = nivel.Nivel if nivel else "No definido"
            sigla_unidad = unidad.Sigla if unidad else ""
            
            print(f"DEBUG LOGIN: Usuario {user.Usuario}")
            print(f"DEBUG LOGIN: ID Rol: {id_rol}, Nombre Rol: {nombre_rol}")
            print(f"DEBUG LOGIN: ID Nivel: {id_nivel}, Nombre Nivel: {nombre_nivel}")
            print(f"DEBUG LOGIN: ID Unidad Académica: {id_unidad}")
            
            # Verificar si tiene contraseña temporal usando bitácora
            from backend.services.usuario_service import has_temporary_password
            temp_password_detected = has_temporary_password(db, user.Id_Usuario)
            print(f"DEBUG: Usuario {user.Usuario} - Contraseña temporal detectada: {temp_password_detected}")
            
            if temp_password_detected:
                # Si tiene contraseña temporal, redirigir a cambiar_password
                response = RedirectResponse(url="/recuperacion/cambiar", status_code=303)
                print(f"DEBUG: Redirigiendo a /recuperacion/cambiar")
            else:
                # Redirigir a la vista principal después de login
                response = RedirectResponse(url="/mod_principal", status_code=303)
                print(f"DEBUG: Redirigiendo a /mod_principal")
            
            # Establecer todas las cookies con la información del usuario
            response.set_cookie(key="id_rol", value=str(id_rol), httponly=True)
            response.set_cookie(key="nombre_rol", value=nombre_rol, httponly=True)
            response.set_cookie(key="id_nivel", value=str(id_nivel), httponly=True)
            response.set_cookie(key="nombre_nivel", value=nombre_nivel, httponly=True)
            if id_usuario:
                response.set_cookie(key="id_usuario", value=str(id_usuario), httponly=True)
            response.set_cookie(key="usuario", value=user.Usuario or "", httponly=True)  # LOGIN del usuario
            response.set_cookie(key="id_unidad_academica", value=str(id_unidad), httponly=True)
            response.set_cookie(key="sigla_unidad_academica", value=sigla_unidad, httponly=True)
            response.set_cookie(key="nombre_usuario", value=user.Nombre or "", httponly=True)
            response.set_cookie(key="apellidoP_usuario", value=user.Paterno or "", httponly=True)
            response.set_cookie(key="apellidoM_usuario", value=user.Materno or "", httponly=True)
            return response
        else:
            mensaje = "Usuario o contraseña incorrectos."
    except Exception as e:
        mensaje = f"Error al validar usuario: {str(e)}"


    return templates.TemplateResponse(
        "login.html",
        {"request": request, "mensaje": mensaje, "exito": exito}
    )


"""@router.post("/", response_model=UsuarioResponse)
async def register_user_endpoint(user: UsuarioCreate, db: Session = Depends(get_db)):
    try:
        return register_usuario(db, user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))"""