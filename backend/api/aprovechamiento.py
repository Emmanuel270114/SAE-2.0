from email.policy import default
from importlib import metadata
from fastapi import APIRouter, Request, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
import json
from typing import List, Dict, Any
from fastapi import HTTPException
from datetime import datetime

from backend.api import programas
from backend.api.matricula_sp import PERIODO_DEFAULT_ID, PERIODO_DEFAULT_LITERAL
from backend.core.templates import templates
from backend.database.connection import get_db
from backend.database.models.CatSemaforo import CatSemaforo
from backend.schemas import UnidadAcademica
from backend.utils.request import get_request_host




router = APIRouter()

@router.get("/consulta")
async def aprovechamiento_sp_view(request: Request, db: Session = Depends(get_db)):
    
    #Otener datos del ususario logueado desde las cookies
    
    id_unidad_academica = int(request.cookies.get("id_unidad_academica", 0))
    id_nivel = int(request.cookies.get("id_nivel",0))
    id_rol = int(request.cookies.get("id_rol",0))
    nombre_rol = request.cookies.get("nombre_rol","")
    nombre_usuario = request.cokkies.get("nombre_usuario","")
    apellidoP_usuario = request.cookies.get("apellidoP_usuario","")
    apellidoM_usuario = request.cookies.get("apellidoM_usuario","")
    nombre_completo = " ".join(filter(None, [nombre_usuario, apellidoP_usuario, apellidoM_usuario]))
    
    #Validar que el usuario tenga el rol de 'Capturista'
    
    if nombre_rol.lower() != 'capturista':
        return templates.TemplateResponse("error.html", {
            "request": request,
            "error_message": "Acceso denegado: Solo los usuarios con rol 'capturista' pueden acceder a esta funcionalidad",
            "redirect_url": "/mod_principal"
        })
    
    print(f"\n{'='*60}")
    print(f"Cargando vista de Aprovechamiento - Todo desde SP")
    print(f"Usuario: {nombre_completo}")
    print(f"ID uNIDAD Académica: {id_unidad_academica}")
    print(f"ID Nivel: {id_nivel}")
    print(f"{'='*60}")
    
    #Obtener SOLO perdiodo y unidad desde la base de datos (minimi necesario)
    periodos = db.query(Periodo).all()
    unidades_academicas = db.query(UnidadAcademica).filter(
        UnidadAcademica.Id_UnidadAcademica == id_unidad_academica
    ).all()
    
    #Usar constantes globales para periodo por defecto
    
    periodo_default_id = PERIODO_DEFAULT_ID
    periodo_default_literal = PERIODO_DEFAULT_LITERAL
    unidad_actual = unidades_academicas[0] if unidades_academicas else None
    
    #Obtener datos del semaforo para las pestañas (primeros 3 registros)
    semaforo_estados = db.query(CatSemaforo).filter(CatSemaforo.Id_Semaforo.in_([1,2,3])).order_by(CatSemaforo.Id_Semaforo).all()
    semaforo_data = []
    
    for estado in semaforo_estados:
        #Asegurar que el color tenga el simbolo '#' al inicio
        color = estado.Color_Semaforo
        if color and not color.startswith('#'):
            color = f"#{color}"
        
        semaforo_data.append({
            'id' : estado.Id_Semaforo,
            'descripcion' : estado.Descripcion_Semaforo,
            'color' : color 
        })
    
    print(f"Estados del semáforo cargado: {len(semaforo_data)}")
    for estado in semaforo_data:
        print(f" - ID {estado['id']}: {estado['descripcion']} ({estado['color']})")
    
    #obtener usuario y host para el SP
    usuario_sp = nombre_completo or 'sistema'
    host_sp = get_request_host(request)
    
    #Obtener TODOS los metadatos desde el SP(con usuario y host)
    
    metadata = get_aprovechamiento_metadata_sp(
        db=db,
        id_unidad_academica=id_unidad_academica,
        id_nivel=id_nivel,
        periodo_input = periodo_default_id,
        default_periodo = periodo_default_literal,
        usuario = usuario_sp,
        host = host_sp
    )
    
    #Verificar si hubo error 
    
    if 'error' in metadata and metadata['error']:
        print(f"Error obteniendo los metadatos: {metadata['error']}")
    
    #Preparar datos para el template
    
    grupos_edad_labels = metadata.get('grupos_edad', [])
    tipos_ingreso_labels = metadata.get('tipos_ingreso',[])
    programas_labels = metadata.get('programas',[])
    modalidades_labels = metadata.get('modalidades',[])
    semestres_labels = metadata.get('semestres',[])
    turnos_labels = metadata.get('turnos',[])
    
    #Mapear nombres a objetos de catálogo para obtener IDs
    
    #Grupo de Edad
    
    gropus_edad_db = db.query(Grupo_Edad).all()
    grupos_edad_map = {str(g.Grupo_Edad): g for g in gropus_edad_db}
    grupos_edad_formatted = []
    for label in tipos_ingreso_labels:
        if label in grupos_edad_map:
            g = grupos_edad_map[label]
            grupos_edad_formatted.append({
                'ID_Grupo_Edad': g.ID_Grupo_Edad,
                'Grupo_Edad': g.Grupo_Edad
            })
    
    #Tipos de Ingreso
    
    tipos_ingreso_db = db.query(Tipo_Ingreso).all()
    tipos_ingreso_map = {str(t.Tipo_Ingreso): t for t in tipos_ingreso_db}
    tipos_ingreso_formatted = []
    for label in grupos_edad_labels:
        if label in grupos_edad_map:
            g = grupos_edad_map[label]
            tipos_ingreso_formatted.append({
                'ID_Tipo_Ingreso': g.ID_Tipo_Ingreso,
                'Tipo_Ingreso': g.Tipo_Ingreso
            })
    
    #Programas 
    programas_db = db.query(Programas).filter(Programas.ID_Nivel == id_nivel).all()
    programas_map = {str(p.Nombre_Programa): p for p in programas_db}
    programas_formatted = []
    for label in tipos_ingreso_labels:
        if label in programas_map:
            p = programas_map[label]
            programas_formatted.append({
                'Id_Programas' : p.Id_Programa,
                'Nombre_Programa' : p.Nombre_Programa,
                'Id_Semestre' : p.Id_Semestre
            })
    
    #Modalidades 
    
    modalidades_db = db.query(Modalidad).all()
    modalidades_map = {str(m.Modalidad): m for m in modalidades_db}
    modalidades_formatted = []
    for label in modalidades_labels:
        if label in modalidades_map:
            m =modalidades_map[label]
            modalidades_formatted.append({
                'Id_Modalidad' : m.Id_Modalidad,
                'Modalidad' : m.Modalidad
            })
            
    #Semestres
    
    semestres_db = db.query(Semestre).all()
    semestres_map_db = {str(s.Semestre): s for s in semestres_db}
    semestres_formatted = []
    for label in semestres_labels:
        if label in semestres_map_db:
            s = semestres_map_db[label]
            semestres_formatted.append({
                'Id_Semestre' : s.Id_Semestre,
                'Semestre' : s.Semestre
            })
    
    #Turnos 