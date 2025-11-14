from fastapi import APIRouter, Request, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Dict, Any
import json

from backend.core.templates import templates
from backend.database.connection import get_db
from backend.utils.request import get_request_host
# Importamos el servicio de matrícula para reutilizar la carga de metadatos (filtros)
from backend.services.matricula_service import get_matricula_metadata_from_sp

# Importamos modelos necesarios para obtener nombres literales
from backend.database.models.CatProgramas import CatProgramas
from backend.database.models.CatModalidad import CatModalidad
from backend.database.models.CatSemestre import CatSemestre
from backend.database.models.CatUnidadAcademica import CatUnidadAcademica
from backend.database.models.CatNivel import CatNivel
from backend.database.models.CatTurno import CatTurno 

router = APIRouter()

# Constantes
PERIODO_DEFAULT_LITERAL = '2025-2026/1'
PERIODO_DEFAULT_ID = 7  # ID correspondiente al periodo por defecto

# === FUNCIÓN AUXILIAR ===
def get_nivel_nombre(db: Session, programa_id: int) -> str:
    """
    Obtiene el nombre del Nivel (ej. 'Medio Superior') basado en el ID del programa.
    """
    try:
        programa = db.query(CatProgramas).filter(CatProgramas.Id_Programa == programa_id).first()
        if not programa:
            return None
        
        nivel = db.query(CatNivel).filter(CatNivel.Id_Nivel == programa.Id_Nivel).first()
        return nivel.Nivel if nivel else None
    except Exception as e:
        print(f"Error obteniendo nivel: {e}")
        return None

# === ENDPOINTS ===

@router.get('/consulta')
async def consulta_aprovechamiento(request: Request, db: Session = Depends(get_db)):
    """
    Carga la vista principal de captura de aprovechamiento.
    """
    # 1. Validación de Rol
    nombre_rol = request.cookies.get("nombre_rol", "")
    if nombre_rol.lower() != 'capturista':
        return templates.TemplateResponse("error.html", {
            "request": request,
            "error_message": "Acceso denegado: Solo los usuarios con rol 'Capturista' pueden acceder a esta funcionalidad.",
            "redirect_url": "/mod_principal/"
        })

    # 2. Obtener datos de sesión desde cookies
    id_unidad_academica = int(request.cookies.get("id_unidad_academica", 0))
    id_nivel = int(request.cookies.get("id_nivel", 0))
    id_rol = int(request.cookies.get("id_rol", 0))
    nombre_usuario = request.cookies.get("nombre_usuario", "")
    apellidoP = request.cookies.get("apellidoP_usuario", "")
    apellidoM = request.cookies.get("apellidoM_usuario", "")
    nombre_completo = " ".join(filter(None, [nombre_usuario, apellidoP, apellidoM]))

    # 3. Obtener Metadatos para Filtros
    usuario_sp = nombre_completo or 'sistema'
    host_sp = get_request_host(request)

    # Llamamos al SP solo para asegurar que se inicialicen cosas si es necesario, 
    # pero usaremos consultas directas para llenar los combos más rápido y seguro.
    try:
        get_matricula_metadata_from_sp(
            db=db,
            id_unidad_academica=id_unidad_academica,
            id_nivel=id_nivel,
            periodo_input=PERIODO_DEFAULT_LITERAL,
            default_periodo=PERIODO_DEFAULT_LITERAL,
            usuario=usuario_sp,
            host=host_sp
        )
    except Exception as e:
        print(f"Nota: Error no crítico al cargar metadatos SP: {e}")

    # 4. Preparar datos para la plantilla usando ORM
    programas_db = db.query(CatProgramas).filter(CatProgramas.Id_Nivel == id_nivel).all()
    programas_fmt = [{'Id_Programa': p.Id_Programa, 'Nombre_Programa': p.Nombre_Programa} for p in programas_db]
    
    modalidades_db = db.query(CatModalidad).all()
    modalidades_fmt = [{'Id_Modalidad': m.Id_Modalidad, 'Modalidad': m.Modalidad} for m in modalidades_db]
    
    semestres_db = db.query(CatSemestre).all()
    semestres_fmt = [{'Id_Semestre': s.Id_Semestre, 'Semestre': s.Semestre} for s in semestres_db]
    
    turnos_db = db.query(CatTurno).all()
    turnos_fmt = [{'Id_Turno': t.Id_Turno, 'Turno': t.Turno} for t in turnos_db]

    return templates.TemplateResponse("aprovechamiento_consulta.html", {
        "request": request,
        "nombre_usuario": nombre_completo,
        "unidad_academica": request.cookies.get("unidad_academica_nombre", "Desconocida"),
        "periodo_actual": PERIODO_DEFAULT_LITERAL,
        # Pasamos las variables IDs explícitamente para el JS
        "id_periodo": PERIODO_DEFAULT_ID,
        "id_unidad_academica": id_unidad_academica,
        # Listas para los combos
        "programas": programas_fmt,
        "modalidades": modalidades_fmt,
        "semestres": semestres_fmt,
        "turnos": turnos_fmt
    })


@router.post('/obtener_datos_sp')
async def obtener_datos_aprovechamiento(request: Request, db: Session = Depends(get_db)):
    """
    Ejecuta SP_Consulta_Aprovechamiento_Unidad_Academica
    """
    try:
        data = await request.json()
        programa_id = data.get('programa')
        
        # Datos de sesión
        unidad_obj = db.query(CatUnidadAcademica).filter(
            CatUnidadAcademica.Id_Unidad_Academica == int(request.cookies.get("id_unidad_academica", 0))
        ).first()
        unidad_sigla = unidad_obj.Sigla if unidad_obj else ''
        
        usuario_login = request.cookies.get("usuario_login") or request.cookies.get("nombre_usuario")
        periodo = PERIODO_DEFAULT_LITERAL 
        host = get_request_host(request)

        # Obtener Nivel literal
        nivel_nombre = get_nivel_nombre(db, int(programa_id))
        if not nivel_nombre:
            return {"error": "No se pudo determinar el Nivel del programa."}

        print(f"Consulta Aprovechamiento: UA={unidad_sigla}, Per={periodo}, Niv={nivel_nombre}")

        # Ejecutar SP
        sql = text("""
            EXEC [dbo].[SP_Consulta_Aprovechamiento_Unidad_Academica]
                 @UUnidad_Academica = :ua,
                 @PPeriodo = :per,
                 @UUsuario = :user,
                 @HHost = :host,
                 @NNivel = :niv
        """)
        
        result = db.execute(sql, {
            'ua': unidad_sigla,
            'per': periodo,
            'user': usuario_login,
            'host': host,
            'niv': nivel_nombre
        })
        
        # Convertir resultados a lista de dicts
        rows = []
        columns = result.keys()
        for row in result.fetchall():
            row_dict = {}
            for i, col in enumerate(columns):
                row_dict[col] = row[i]
            rows.append(row_dict)

        return {"rows": rows}

    except Exception as e:
        print(f"Error en obtener_datos_aprovechamiento: {e}")
        return {"error": str(e)}


@router.post('/guardar_captura_temp')
async def guardar_captura_temp(request: Request, db: Session = Depends(get_db)):
    """
    Guarda en Temp_Aprovechamiento.
    """
    try:
        data = await request.json()
        grid_data = data.get('gridData', [])
        
        if not grid_data:
            return {"error": "No hay datos para guardar"}

        # 1. Limpiar tabla temporal
        db.execute(text("TRUNCATE TABLE Temp_Aprovechamiento"))
        
        # 2. Insertar datos
        sql_insert = text("""
            INSERT INTO Temp_Aprovechamiento (
                Id_Periodo, Id_Unidad_Academica, Id_Programa, Id_Rama, 
                Id_Nivel, Id_Modalidad, Id_Turno, Id_Semestre, Id_Sexo, 
                Id_Aprovechamiento, Aprovechamiento
            )
            VALUES (:p, :ua, :prog, :rama, :niv, :mod, :tur, :sem, :sex, :aprov, :val)
        """)

        for row in grid_data:
            db.execute(sql_insert, {
                'p': int(row['id_periodo']),
                'ua': int(row['id_unidad_academica']),
                'prog': int(row['id_programa']),
                'rama': int(row['id_rama']),
                'niv': int(row['id_nivel']),
                'mod': int(row['id_modalidad']),
                'tur': int(row['id_turno']),
                'sem': int(row['id_semestre']),
                'sex': int(row['id_sexo']),
                'aprov': int(row['id_aprovechamiento']),
                'val': int(row['valor']) if row['valor'] is not None else None
            })

        db.commit()
        return {"success": True, "message": "Datos guardados en temporal"}

    except Exception as e:
        db.rollback()
        print(f"Error guardar temp: {e}")
        return {"error": str(e)}


@router.post('/actualizar_aprovechamiento')
async def actualizar_aprovechamiento(request: Request, db: Session = Depends(get_db)):
    """
    Ejecuta SP_Actualiza_Aprovechamiento_Por_Unidad_Academica
    """
    try:
        data = await request.json()
        programa_id = data.get('programa')

        # Datos de sesión
        unidad_obj = db.query(CatUnidadAcademica).filter(
            CatUnidadAcademica.Id_Unidad_Academica == int(request.cookies.get("id_unidad_academica", 0))
        ).first()
        unidad_sigla = unidad_obj.Sigla if unidad_obj else ''
        
        usuario_login = request.cookies.get("usuario_login") or request.cookies.get("nombre_usuario")
        periodo = PERIODO_DEFAULT_LITERAL
        host = get_request_host(request)
        nivel_nombre = get_nivel_nombre(db, int(programa_id))

        sql = text("""
            EXEC [dbo].[SP_Actualiza_Aprovechamiento_Por_Unidad_Academica]
                 @UUnidad_Academica = :ua,
                 @UUsuario = :user,
                 @PPeriodo = :per,
                 @HHost = :host,
                 @NNivel = :niv
        """)

        db.execute(sql, {
            'ua': unidad_sigla,
            'user': usuario_login,
            'per': periodo,
            'host': host,
            'niv': nivel_nombre
        })
        db.commit()

        return {"success": True, "message": "Aprovechamiento actualizado correctamente."}

    except Exception as e:
        db.rollback()
        print(f"Error actualizar aprovechamiento: {e}")
        return {"error": str(e)}


@router.post('/finalizar_semestre')
async def finalizar_semestre(request: Request, db: Session = Depends(get_db)):
    """
    Ejecuta SP_Actualiza_Aprovechamiento_Por_Semestre_AU
    """
    try:
        data = await request.json()
        
        # Obtener nombres literales desde la BD usando los IDs recibidos
        unidad_obj = db.query(CatUnidadAcademica).filter(
            CatUnidadAcademica.Id_Unidad_Academica == int(request.cookies.get("id_unidad_academica", 0))
        ).first()
        unidad_sigla = unidad_obj.Sigla if unidad_obj else ''

        programa = db.query(CatProgramas).filter(CatProgramas.Id_Programa == int(data['programa'])).first()
        modalidad = db.query(CatModalidad).filter(CatModalidad.Id_Modalidad == int(data['modalidad'])).first()
        semestre = db.query(CatSemestre).filter(CatSemestre.Id_Semestre == int(data['semestre'])).first()
        
        usuario_login = request.cookies.get("usuario_login") or request.cookies.get("nombre_usuario")
        host = get_request_host(request)
        nivel_nombre = get_nivel_nombre(db, int(data['programa']))

        sql = text("""
            EXEC [dbo].[SP_Actualiza_Aprovechamiento_Por_Semestre_AU]
                 @UUnidad_Academica = :ua,
                 @PPrograma = :prog,
                 @MModalidad = :mod,
                 @SSemestre = :sem,
                 @UUsuario = :user,
                 @PPeriodo = :per,
                 @HHost = :host,
                 @NNivel = :niv
        """)

        db.execute(sql, {
            'ua': unidad_sigla,
            'prog': programa.Nombre_Programa,
            'mod': modalidad.Modalidad,
            'sem': semestre.Semestre,
            'user': usuario_login,
            'per': PERIODO_DEFAULT_LITERAL,
            'host': host,
            'niv': nivel_nombre
        })
        db.commit()

        return {"success": True, "message": f"Semestre {semestre.Semestre} finalizado."}

    except Exception as e:
        db.rollback()
        print(f"Error finalizar semestre: {e}")
        return {"error": str(e)}