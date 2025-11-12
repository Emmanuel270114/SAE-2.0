from fastapi import APIRouter, Request, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
import json
from typing import List, Dict, Any
from fastapi import HTTPException
from datetime import datetime

from backend.core.templates import templates
from backend.database.connection import get_db
from backend.database.models.Matricula import Matricula
from backend.database.models.CatPeriodo import CatPeriodo as Periodo
from backend.database.models.CatUnidadAcademica import CatUnidadAcademica as Unidad_Academica
from backend.database.models.CatNivel import CatNivel as Nivel
from backend.database.models.CatSemestre import CatSemestre as Semestre
from backend.database.models.CatProgramas import CatProgramas as Programas
from backend.database.models.CatModalidad import CatModalidad as Modalidad
from backend.database.models.CatTurno import CatTurno as Turno
from backend.database.models.CatGrupoEdad import CatGrupoEdad as Grupo_Edad
from backend.database.models.CatTipoIngreso import TipoIngreso as Tipo_Ingreso
from backend.database.models.CatRama import CatRama as Rama
from backend.database.models.CatSemaforo import CatSemaforo
from backend.services.matricula_service import (
    execute_matricula_sp_with_context,
    get_matricula_metadata_from_sp,
    execute_sp_actualiza_matricula_por_unidad_academica,
    execute_sp_actualiza_matricula_por_semestre_au,
    get_estado_semaforo_desde_sp,
)
from backend.utils.request import get_request_host
from backend.database.models.Temp_Matricula import Temp_Matricula

router = APIRouter()

# Constantes globales
PERIODO_DEFAULT_ID = 7
PERIODO_DEFAULT_LITERAL = '2025-2026/1'


@router.get('/consulta')
async def captura_matricula_sp_view(request: Request, db: Session = Depends(get_db)):
    """
    Endpoint principal para la visualización/captura de matrícula usando EXCLUSIVAMENTE Stored Procedures.
    Accesible para:
    - Rol 'Capturista' (ID 3): Captura y validación de datos
    - Roles con ID 4 y 5: Solo visualización y validación/rechazo (sin edición)
    TODA la información viene del SP, NO de los modelos ORM.
    """
    # Obtener datos del usuario logueado desde las cookies
    id_unidad_academica = int(request.cookies.get("id_unidad_academica", 0))
    id_nivel = int(request.cookies.get("id_nivel", 0))
    id_rol = int(request.cookies.get("id_rol", 0))
    nombre_rol = request.cookies.get("nombre_rol", "")
    nombre_usuario = request.cookies.get("nombre_usuario", "")
    apellidoP_usuario = request.cookies.get("apellidoP_usuario", "")
    apellidoM_usuario = request.cookies.get("apellidoM_usuario", "")
    nombre_completo = " ".join(filter(None, [nombre_usuario, apellidoP_usuario, apellidoM_usuario]))

    # Validar que el usuario tenga uno de los roles permitidos
    roles_permitidos = [3, 4, 5]  # 3=Capturista, 4 y 5=Roles de validación/rechazo
    if id_rol not in roles_permitidos:
        return templates.TemplateResponse("error.html", {
            "request": request,
            "error_message": f"Acceso denegado: Su rol ({nombre_rol}) no tiene permisos para acceder a esta funcionalidad.",
            "redirect_url": "/mod_principal/"
        })
    
    # Determinar el modo de vista según el rol
    es_capturista = (id_rol == 3)
    modo_vista = "captura" if es_capturista else "validacion"

    print(f"\n{'='*60}")
    print(f"CARGANDO VISTA DE MATRÍCULA - TODO DESDE SP")
    print(f"Usuario: {nombre_completo}")
    print(f"Rol: {nombre_rol} (ID: {id_rol})")
    print(f"Modo de vista: {modo_vista.upper()}")
    print(f"ID Unidad Académica: {id_unidad_academica}")
    print(f"ID Nivel: {id_nivel}")
    print(f"{'='*60}")

    # Obtener SOLO período y unidad desde la base de datos (mínimo necesario)
    periodos = db.query(Periodo).all()
    unidades_academicas = db.query(Unidad_Academica).filter(
        Unidad_Academica.Id_Unidad_Academica == id_unidad_academica
    ).all()
    
    # Usar constantes globales para periodo por defecto
    periodo_default_id = PERIODO_DEFAULT_ID
    periodo_default_literal = PERIODO_DEFAULT_LITERAL
    unidad_actual = unidades_academicas[0] if unidades_academicas else None

    # Obtener datos del semáforo para las pestañas (primeros 3 registros)
    semaforo_estados = db.query(CatSemaforo).filter(CatSemaforo.Id_Semaforo.in_([1, 2, 3])).order_by(CatSemaforo.Id_Semaforo).all()
    semaforo_data = []
    for estado in semaforo_estados:
        # Asegurar que el color tenga el símbolo # al inicio
        color = estado.Color_Semaforo
        if color and not color.startswith('#'):
            color = f"#{color}"
        
        semaforo_data.append({
            'id': estado.Id_Semaforo,
            'descripcion': estado.Descripcion_Semaforo,
            'color': color
        })
    
    print(f"📊 Estados del semáforo cargados: {len(semaforo_data)}")
    for estado in semaforo_data:
        print(f"  - ID {estado['id']}: {estado['descripcion']} ({estado['color']})")

    # Obtener usuario y host para el SP
    usuario_sp = nombre_completo or 'sistema'
    host_sp = get_request_host(request)

    # Obtener TODOS los metadatos desde el SP (con usuario y host)
    metadata = get_matricula_metadata_from_sp(
        db=db,
        id_unidad_academica=id_unidad_academica,
        id_nivel=id_nivel,
        periodo_input=periodo_default_literal,
        default_periodo=periodo_default_literal,
        usuario=usuario_sp,
        host=host_sp
    )

    # Verificar si hubo error
    if 'error' in metadata and metadata['error']:
        print(f"⚠️ Error obteniendo metadatos: {metadata['error']}")

    # Preparar datos para el template
    grupos_edad_labels = metadata.get('grupos_edad', [])
    tipos_ingreso_labels = metadata.get('tipos_ingreso', [])
    programas_labels = metadata.get('programas', [])
    modalidades_labels = metadata.get('modalidades', [])
    semestres_labels = metadata.get('semestres', [])
    turnos_labels = metadata.get('turnos', [])

    # Mapear nombres a objetos de catálogo para obtener IDs
    # Grupos de Edad
    grupos_edad_db = db.query(Grupo_Edad).all()
    grupos_edad_map = {str(g.Grupo_Edad): g for g in grupos_edad_db}
    grupos_edad_formatted = []
    for label in grupos_edad_labels:
        if label in grupos_edad_map:
            g = grupos_edad_map[label]
            grupos_edad_formatted.append({'Id_Grupo_Edad': g.Id_Grupo_Edad, 'Grupo_Edad': g.Grupo_Edad})
    
    # Tipos de Ingreso
    tipos_ingreso_db = db.query(Tipo_Ingreso).all()
    tipos_ingreso_map = {str(t.Tipo_de_Ingreso): t for t in tipos_ingreso_db}
    tipos_ingreso_formatted = []
    for label in tipos_ingreso_labels:
        if label in tipos_ingreso_map:
            t = tipos_ingreso_map[label]
            tipos_ingreso_formatted.append({'Id_Tipo_Ingreso': t.Id_Tipo_Ingreso, 'Tipo_de_Ingreso': t.Tipo_de_Ingreso})
    
    # Programas
    programas_db = db.query(Programas).filter(Programas.Id_Nivel == id_nivel).all()
    programas_map = {str(p.Nombre_Programa): p for p in programas_db}
    programas_formatted = []
    for label in programas_labels:
        if label in programas_map:
            p = programas_map[label]
            programas_formatted.append({
                'Id_Programa': p.Id_Programa,
                'Nombre_Programa': p.Nombre_Programa,
                'Id_Semestre': p.Id_Semestre
            })
    
    # Modalidades
    modalidades_db = db.query(Modalidad).all()
    modalidades_map = {str(m.Modalidad): m for m in modalidades_db}
    modalidades_formatted = []
    for label in modalidades_labels:
        if label in modalidades_map:
            m = modalidades_map[label]
            modalidades_formatted.append({'Id_Modalidad': m.Id_Modalidad, 'Modalidad': m.Modalidad})
    
    # Semestres
    semestres_db = db.query(Semestre).all()
    semestres_map_db = {str(s.Semestre): s for s in semestres_db}
    semestres_formatted = []
    for label in semestres_labels:
        if label in semestres_map_db:
            s = semestres_map_db[label]
            semestres_formatted.append({'Id_Semestre': s.Id_Semestre, 'Semestre': s.Semestre})
    
    # Turnos
    turnos_db = db.query(Turno).all()
    turnos_map = {str(t.Turno): t for t in turnos_db}
    turnos_formatted = []
    for label in turnos_labels:
        if label in turnos_map:
            t = turnos_map[label]
            turnos_formatted.append({'Id_Turno': t.Id_Turno, 'Turno': t.Turno})

    # Construir un mapping simple para semestres
    semestres_map_json_dict = {s['Id_Semestre']: s['Semestre'] for s in semestres_formatted}
    semestres_map_json = json.dumps(semestres_map_json_dict, ensure_ascii=False)

    print(f"\n=== METADATOS ENVIADOS AL FRONTEND ===")
    print(f"Grupos de Edad: {len(grupos_edad_formatted)} -> {[g['Grupo_Edad'] for g in grupos_edad_formatted]}")
    print(f"Tipos de Ingreso: {len(tipos_ingreso_formatted)} -> {[t['Tipo_de_Ingreso'] for t in tipos_ingreso_formatted]}")
    print(f"Programas: {len(programas_formatted)} -> {[p['Nombre_Programa'] for p in programas_formatted]}")
    print(f"Modalidades: {len(modalidades_formatted)}")
    print(f"Semestres: {len(semestres_formatted)}")
    print(f"Turnos: {len(turnos_formatted)}")

    return templates.TemplateResponse("matricula_consulta.html", {
        "request": request,
        "nombre_usuario": nombre_completo,
        "nombre_rol": nombre_rol,
        "id_unidad_academica": id_unidad_academica,
        "id_nivel": id_nivel,
        "id_rol": id_rol,
        "es_capturista": es_capturista,
        "modo_vista": modo_vista,
        "periodos": periodos,
        "unidades_academicas": unidades_academicas,
        "periodo_default_id": periodo_default_id,
        "periodo_default_literal": periodo_default_literal,
        "unidad_actual": unidad_actual,
        "programas": programas_formatted,
        "modalidades": modalidades_formatted,
        "semestres": semestres_formatted,
        "semestres_map_json": semestres_map_json,
        "turnos": turnos_formatted,
        "grupos_edad": grupos_edad_formatted,
        "tipos_ingreso": tipos_ingreso_formatted,
        "semaforo_estados": semaforo_data
    })

# Endpoint para obtener datos existentes usando SP
@router.post("/obtener_datos_existentes_sp")
async def obtener_datos_existentes_sp(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Endpoint para obtener datos existentes usando SP.
    Retorna SOLO las filas del SP sin procesamiento adicional.
    El frontend se encarga de construir la tabla con estos datos.
    """
    try:
        data = await request.json()
        print(f"\n=== DEBUG SP - Parámetros recibidos ===")
        print(f"Datos JSON: {data}")

        # Obtener parámetros del JSON
        periodo = data.get('periodo')
        
        # Obtener datos del usuario desde cookies
        id_unidad_academica = int(request.cookies.get("id_unidad_academica", 0))
        id_nivel = int(request.cookies.get("id_nivel", 0))
        nombre_usuario = request.cookies.get("nombre_usuario", "")
        apellidoP_usuario = request.cookies.get("apellidoP_usuario", "")
        apellidoM_usuario = request.cookies.get("apellidoM_usuario", "")
        nombre_completo = " ".join(filter(None, [nombre_usuario, apellidoP_usuario, apellidoM_usuario]))

        print(f"ID Unidad Académica (cookie): {id_unidad_academica}")
        print(f"ID Nivel (cookie): {id_nivel}")
        print(f"Usuario: {nombre_completo}")

        # Obtener usuario y host para el SP
        usuario_sp = nombre_completo or 'sistema'
        host_sp = get_request_host(request)
        print(f"Host: {host_sp}")

        # Ejecutar SP y obtener metadatos (con usuario y host)
        rows_list, metadata, debug_msg = execute_matricula_sp_with_context(
            db=db,
            id_unidad_academica=id_unidad_academica,
            id_nivel=id_nivel,
            periodo_input=periodo,
            default_periodo='2025-2026/1',
            usuario=usuario_sp,
            host=host_sp
        )
        
        print(f"\n=== RESULTADOS DEL SP ===")
        print(debug_msg)
        print(f"Total de filas: {len(rows_list)}")
        print(f"Metadatos extraídos: {metadata}")

        # Devolver resultado exitoso o error
        if "Error" in debug_msg:
            return {"error": debug_msg}
        else:
            return {
                "rows": rows_list,
                "metadata": metadata,
                "debug": debug_msg
            }

    except Exception as e:
        print(f"ERROR en endpoint SP: {str(e)}")
        import traceback
        traceback.print_exc()
        return {"error": f"Error al obtener datos existentes: {str(e)}"}

# Endpoint de depuración detallada del SP
@router.get('/debug_sp')
async def debug_sp(request: Request, db: Session = Depends(get_db)):
    """Endpoint de depuración que usa el servicio (sin SQL crudo aquí)."""
    try:
        id_unidad_academica = int(request.cookies.get("id_unidad_academica", 0))
        id_nivel = int(request.cookies.get("id_nivel", 0))
        nombre_usuario = request.cookies.get("nombre_usuario", "")
        apellidoP_usuario = request.cookies.get("apellidoP_usuario", "")
        apellidoM_usuario = request.cookies.get("apellidoM_usuario", "")
        nombre_completo = " ".join(filter(None, [nombre_usuario, apellidoP_usuario, apellidoM_usuario]))
        usuario_sp = nombre_completo or 'sistema'
        host_sp = get_request_host(request)

        periodo = '2025-2026/1'
        rows, metadata, debug_msg = execute_matricula_sp_with_context(
            db,
            id_unidad_academica,
            id_nivel,
            periodo,
            periodo,
            usuario_sp,
            host_sp,
        )
        columnas = list(rows[0].keys()) if rows else []
        return {
            "mensaje": debug_msg,
            "total_filas": len(rows),
            "columnas": columnas,
            "primera_fila": rows[0] if rows else None,
            "metadata": metadata,
        }
    except Exception as e:
        return {"error": str(e)}

@router.get('/semestres_map')
async def semestres_map_sp(db: Session = Depends(get_db)):
    """Endpoint para obtener el mapeo de semestres (Id -> Nombre)"""
    try:
        semestres = db.query(Semestre).all()
        semestres_map = {s.Id_Semestre: s.Semestre for s in semestres}
        return semestres_map
    except Exception as e:
        return {"error": str(e)}

@router.post("/guardar_captura_completa")
async def guardar_captura_completa(request: Request, db: Session = Depends(get_db)):
    """
    Guardar la captura completa de matrícula enviada desde el frontend.
    Convierte el formato del frontend al modelo Temp_Matricula.
    """
    try:
        data = await request.json()
        print(f"\n=== GUARDANDO CAPTURA COMPLETA ===")
        print(f"Datos recibidos: {data}")
        
        # Obtener datos del usuario desde cookies
        nombre_usuario = request.cookies.get("nombre_usuario", "")
        apellidoP_usuario = request.cookies.get("apellidoP_usuario", "")
        apellidoM_usuario = request.cookies.get("apellidoM_usuario", "")
        nombre_completo = " ".join(filter(None, [nombre_usuario, apellidoP_usuario, apellidoM_usuario]))
        
        # Obtener usuario y host
        usuario_sp = nombre_completo or 'sistema'
        host_sp = get_request_host(request)
        
        # Extraer información base
        periodo_input = data.get('periodo')
        programa = data.get('programa')
        semestre = data.get('semestre')
        modalidad = data.get('modalidad')
        turno = data.get('turno')
        total_grupos = data.get('total_grupos')
        datos_matricula = data.get('datos_matricula', {})
        
        # Convertir período de ID a formato literal para guardar en Temp_Matricula
        if periodo_input:
            if str(periodo_input).isdigit():
                # Buscar el período por ID
                periodo_obj = db.query(Periodo).filter(Periodo.Id_Periodo == int(periodo_input)).first()
                if periodo_obj:
                    periodo = periodo_obj.Periodo  # '2025-2026/1'
                
                    print(f"🔄 Período convertido de ID {periodo_input} → '{periodo}' para Temp_Matricula")
                else:
                    print(f"⚠️ ID de período {periodo_input} no encontrado, usando default")
                    periodo = PERIODO_DEFAULT_LITERAL
            else:
                # Ya es formato literal
                periodo = str(periodo_input)
                print(f"✅ Período ya en formato literal: '{periodo}'")
        else:
            periodo = PERIODO_DEFAULT_LITERAL
            print(f"📌 Usando período por defecto: '{periodo}'")
        
        if not datos_matricula:
            return {"error": "No se encontraron datos de matrícula para guardar"}
        
        # Obtener campos válidos del modelo Temp_Matricula
        valid_fields = set(Temp_Matricula.__annotations__.keys())
        print(f"Campos válidos Temp_Matricula: {valid_fields}")
        
        # Obtener nombres desde la base de datos para mapear IDs
        programa_obj = db.query(Programas).filter(Programas.Id_Programa == int(programa)).first()
        modalidad_obj = db.query(Modalidad).filter(Modalidad.Id_Modalidad == int(modalidad)).first()
        turno_obj = db.query(Turno).filter(Turno.Id_Turno == int(turno)).first()
        semestre_obj = db.query(Semestre).filter(Semestre.Id_Semestre == int(semestre)).first()
        
        # Obtener Nombre_Rama desde el programa
        rama_obj = None
        if programa_obj and programa_obj.Id_Rama_Programa:
            rama_obj = db.query(Rama).filter(Rama.Id_Rama == programa_obj.Id_Rama_Programa).first()

        # Obtener sigla de la unidad académica y nivel desde cookies
        id_unidad_academica = int(request.cookies.get("id_unidad_academica", 0))
        id_nivel = int(request.cookies.get("id_nivel", 0))
        
        unidad_obj = db.query(Unidad_Academica).filter(
            Unidad_Academica.Id_Unidad_Academica == id_unidad_academica
        ).first()
        
        nivel_obj = db.query(Nivel).filter(Nivel.Id_Nivel == id_nivel).first()
        
        # Obtener mapeos de grupos de edad y tipos de ingreso para convertir a nombres
        grupos_edad_db = db.query(Grupo_Edad).all()
        grupos_edad_map = {str(g.Id_Grupo_Edad): g.Grupo_Edad for g in grupos_edad_db}
        
        tipos_ingreso_db = db.query(Tipo_Ingreso).all()
        tipos_ingreso_map = {str(t.Id_Tipo_Ingreso): t.Tipo_de_Ingreso for t in tipos_ingreso_db}
        
        registros_insertados = 0
        registros_rechazados = 0
        
        # Limpiar la sesión para evitar conflictos de identidad
        db.expunge_all()
        
        # Obtener el semestre seleccionado como número
        semestre_numero = None
        if semestre_obj:
            try:
                # Extraer el número del semestre (ej: "1" de "Primer Semestre", "2" de "Segundo Semestre")
                semestre_text = semestre_obj.Semestre.lower()
                if "primer" in semestre_text or semestre_text == "1":
                    semestre_numero = 1
                elif "segundo" in semestre_text or semestre_text == "2":
                    semestre_numero = 2
                elif "tercer" in semestre_text or semestre_text == "3":
                    semestre_numero = 3
                # Agregar más semestres según sea necesario
            except:
                pass
        
        print(f"Semestre detectado: {semestre_numero} (de: {semestre_obj.Semestre if semestre_obj else 'N/A'})")
        
        # Procesar cada registro de matrícula
        for key, dato in datos_matricula.items():
            # Validación de reglas de semestre - SEGURIDAD BACKEND
            tipo_ingreso_id = str(dato.get('tipo_ingreso', ''))
            
            # Aplicar reglas de validación por semestre
            if semestre_numero is not None and tipo_ingreso_id:
                # Regla 1: Semestre 1 no puede tener "Reingreso" (ID: 2)
                if semestre_numero == 1 and tipo_ingreso_id == "2":
                    print(f"VALIDACIÓN RECHAZADA: Semestre 1 no puede tener Reingreso (tipo_ingreso: {tipo_ingreso_id})")
                    registros_rechazados += 1
                    continue  # Saltar este registro
                
                # Regla 2: Semestres diferentes a 1 no pueden tener "Nuevo Ingreso" (ID: 1)
                if semestre_numero != 1 and tipo_ingreso_id == "1":
                    print(f"VALIDACIÓN RECHAZADA: Semestre {semestre_numero} no puede tener Nuevo Ingreso (tipo_ingreso: {tipo_ingreso_id})")
                    registros_rechazados += 1
                    continue  # Saltar este registro
            
            # Mapear grupo_edad ID a nombre completo
            grupo_edad_id = str(dato.get('grupo_edad', ''))
            grupo_edad_nombre = grupos_edad_map.get(grupo_edad_id, grupo_edad_id)
            
            # Mapear tipo_ingreso ID a nombre completo
            tipo_ingreso_nombre = tipos_ingreso_map.get(tipo_ingreso_id, tipo_ingreso_id)
            
            # Convertir sexo de M/F a Hombre/Mujer
            sexo_corto = dato.get('sexo', '')
            if sexo_corto == 'M':
                sexo_completo = 'Hombre'
            elif sexo_corto == 'F':
                sexo_completo = 'Mujer'
            else:
                sexo_completo = sexo_corto
            
            # Construir registro para Temp_Matricula
            registro = {
                'Periodo': periodo,
                'Sigla': unidad_obj.Sigla if unidad_obj else 'UNK',
                'Nombre_Programa': programa_obj.Nombre_Programa if programa_obj else '',
                'Nombre_Rama': rama_obj.Nombre_Rama if rama_obj else 'NULL',
                'Nivel': nivel_obj.Nivel if nivel_obj else '',
                'Modalidad': modalidad_obj.Modalidad if modalidad_obj else '',
                'Turno': turno_obj.Turno if turno_obj else '',
                'Semestre': semestre_obj.Semestre if semestre_obj else '',
                'Grupo_Edad': grupo_edad_nombre,
                'Tipo_Ingreso': tipo_ingreso_nombre,
                'Sexo': sexo_completo,
                'Matricula': int(dato.get('matricula', 0)),
                'Salones': int(dato.get('salones', total_grupos))
            }
            
            # Filtrar solo campos válidos
            filtered = {k: v for k, v in registro.items() if k in valid_fields}
            
            # Cambiar condición para incluir valores de 0 (>= 0 en lugar de > 0)
            if filtered and filtered.get('Matricula', 0) >= 0:
                # Usar merge() para manejar automáticamente INSERT/UPDATE
                temp_matricula = Temp_Matricula(**filtered)
                merged_obj = db.merge(temp_matricula)
                
                registros_insertados += 1
                print(f"Registro procesado (merge): {filtered}")
        
        db.commit()
        
        # Construir mensaje informativo
        mensaje_base = f"Matrícula procesada. {registros_insertados} registros guardados"
        if registros_rechazados > 0:
            mensaje_base += f", {registros_rechazados} registros rechazados por validación de semestre"
        mensaje_base += "."
        
        return {
            "mensaje": mensaje_base,
            "registros_insertados": registros_insertados,
            "registros_rechazados": registros_rechazados,
            "validacion_aplicada": semestre_numero is not None
        }
        
    except Exception as e:
        db.rollback()
        print(f"ERROR al guardar captura completa: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error al guardar la matrícula: {str(e)}")

@router.post("/guardar_progreso")
def guardar_progreso(datos: List[Dict[str, Any]], db: Session = Depends(get_db)):
    """
    Guardar el progreso de la matrícula en la tabla Temp_Matricula.
    Args:
        datos: Lista de diccionarios con los datos de la matrícula.
        db: Sesión de base de datos.
    Returns:
        Mensaje de éxito o error.
    """
    try:
        # Obtener campos válidos desde el modelo Temp_Matricula
        valid_fields = set()
        # Intentar leer anotaciones (Python typing) si están presentes
        try:
            valid_fields = set(Temp_Matricula.__annotations__.keys())
        except Exception:
            # Fallback: leer atributos públicos definidos en la clase
            valid_fields = {k for k in dir(Temp_Matricula) if not k.startswith('_')}

        print(f"Campos válidos Temp_Matricula: {valid_fields}")

        # Limpiar la sesión para evitar conflictos de identidad
        db.expunge_all()

        for dato in datos:
            # Filtrar solo las claves que estén en el modelo
            filtered = {k: v for k, v in dato.items() if k in valid_fields}
            if not filtered:
                # Si no hay campos válidos, saltar
                print(f"Advertencia: entrada sin campos válidos será ignorada: {dato}")
                continue
            
            # Usar merge() para manejar automáticamente INSERT/UPDATE
            temp_matricula = Temp_Matricula(**filtered)
            merged_obj = db.merge(temp_matricula)
            print(f"Registro procesado (merge) en guardar_progreso: {filtered}")

        db.commit()
        return {"message": "Progreso guardado exitosamente."}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error al guardar el progreso: {str(e)}")

@router.post("/actualizar_matricula")
async def actualizar_matricula(request: Request, db: Session = Depends(get_db)):
    """
    Ejecuta el SP SP_Actualiza_Matricula_Por_Unidad_Academica para actualizar 
    la tabla Matricula con los datos de Temp_Matricula y luego limpiar la tabla temporal.
    """
    try:
        # Obtener datos del usuario desde cookies
        nombre_usuario = request.cookies.get("nombre_usuario", "")
        apellidoP_usuario = request.cookies.get("apellidoP_usuario", "")
        apellidoM_usuario = request.cookies.get("apellidoM_usuario", "")
        nombre_completo = " ".join(filter(None, [nombre_usuario, apellidoP_usuario, apellidoM_usuario]))
        
        # Obtener unidad académica desde cookies (si no está, resolver vía Id_Unidad_Academica)
        unidad_sigla = request.cookies.get("unidad_sigla", "")
        if not unidad_sigla:
            try:
                id_unidad_cookie = int(request.cookies.get("id_unidad_academica", 0))
            except Exception:
                id_unidad_cookie = 0
            if id_unidad_cookie:
                unidad_obj = db.query(Unidad_Academica).filter(Unidad_Academica.Id_Unidad_Academica == id_unidad_cookie).first()
                if unidad_obj and unidad_obj.Sigla:
                    unidad_sigla = unidad_obj.Sigla
                    print(f"🛠️ Resuelta unidad_sigla desde Id_Unidad_Academica cookie: {unidad_sigla}")
                else:
                    print("⚠️ No se pudo resolver unidad_sigla desde Id_Unidad_Academica")
            else:
                print("⚠️ Cookie unidad_sigla ausente y no hay Id_Unidad_Academica válido")

        # Obtener usuario y host
        usuario_sp = nombre_completo or 'sistema'
        host_sp = get_request_host(request)
        
        # Obtener período y total_grupos desde el request o usar valores por defecto
        data = await request.json()
        periodo_input = data.get('periodo')
        total_grupos = data.get('total_grupos', 0)
        
        # SIEMPRE convertir a formato literal para el SP
        if periodo_input:
            # Si es un ID numérico (como '7'), convertir a literal
            if str(periodo_input).isdigit():
                # Buscar el período por ID en la base de datos
                periodo_obj = db.query(Periodo).filter(Periodo.Id_Periodo == int(periodo_input)).first()
                if periodo_obj:
                    periodo = periodo_obj.Periodo  # '2025-2026/1'
                
                    print(f"🔄 Convertido ID {periodo_input} → '{periodo}'")
                else:
                    print(f"⚠️ ID de período {periodo_input} no encontrado, usando default")
                    periodo = PERIODO_DEFAULT_LITERAL
            else:
                # Ya es formato literal, usarlo directamente
                periodo = str(periodo_input)
                print(f"✅ Período ya en formato literal: '{periodo}'")
        else:
            # No viene período, usar el default literal
            periodo = PERIODO_DEFAULT_LITERAL
            print(f"📌 Usando período por defecto: '{periodo}'")
            
        nivel = request.cookies.get("nombre_nivel", "")  # Obtener el nombre del nivel desde cookies
        
        if not periodo:
            raise HTTPException(status_code=400, detail="Período es requerido para actualizar la matrícula")
        
        print(f"\n=== ACTUALIZANDO MATRÍCULA ===")
        print(f"Usuario: {usuario_sp}")
        print(f"Período: {periodo}")
        print(f"Host: {host_sp}")
        print(f"Nivel: {nivel}")
        print(f"ID Nivel desde cookies: {request.cookies.get('id_nivel', 'No encontrado')}")
        print(f"Nombre Nivel desde cookies: {request.cookies.get('nombre_nivel', 'No encontrado')}")
        print(f"Cookies disponibles: {list(request.cookies.keys())}")
        
        # Verificar que hay datos en Temp_Matricula antes de actualizar
        temp_count = db.query(Temp_Matricula).count()
        if temp_count == 0:
            return {
                "warning": "No hay datos en Temp_Matricula para actualizar",
                "registros_temp": 0,
                "registros_actualizados": 0
            }
        
        print(f"Registros en Temp_Matricula: {temp_count}")
        
        # DIAGNÓSTICO: Mostrar contenido de Temp_Matricula antes de actualizar
        print(f"\n=== DIAGNÓSTICO TEMP_MATRICULA ===")
        temp_records = db.query(Temp_Matricula).all()
        for i, record in enumerate(temp_records, 1):
            print(f"Registro {i}:")
            print(f"  Periodo: '{record.Periodo}'")
            print(f"  Sigla: '{record.Sigla}'")
            print(f"  Nombre_Programa: '{record.Nombre_Programa}'")
            print(f"  Nombre_Rama: '{record.Nombre_Rama}'")
            print(f"  Nivel: '{record.Nivel}'")
            print(f"  Modalidad: '{record.Modalidad}'")
            print(f"  Turno: '{record.Turno}'")
            print(f"  Semestre: '{record.Semestre}'")
            print(f"  Grupo_Edad: '{record.Grupo_Edad}'")
            print(f"  Tipo_Ingreso: '{record.Tipo_Ingreso}'")
            print(f"  Sexo: '{record.Sexo}'")
            print(f"  Matricula: {record.Matricula}")
            print("-" * 40)
        
        # DIAGNÓSTICO: Verificar si existen registros en Matricula que coincidan
        print(f"\n=== VERIFICANDO COINCIDENCIAS EN MATRICULA ===")
        matricula_count = db.query(Matricula).count()
        print(f"Total registros en Matricula: {matricula_count}")
        
        # Buscar un registro de ejemplo para ver si hay coincidencias
        if temp_records:
            temp_ejemplo = temp_records[0]
            print(f"\nBuscando coincidencias para el primer registro de Temp_Matricula:")
            
            # Verificar periodo
            periodo_match = db.query(Periodo).filter(Periodo.Periodo == temp_ejemplo.Periodo).first()
            print(f"Periodo '{temp_ejemplo.Periodo}' encontrado: {periodo_match is not None}")
            if periodo_match:
                print(f"  ID Periodo: {periodo_match.Id_Periodo}")
            
            # Verificar unidad académica
            unidad_match = db.query(Unidad_Academica).filter(Unidad_Academica.Sigla == temp_ejemplo.Sigla).first()
            print(f"Unidad '{temp_ejemplo.Sigla}' encontrada: {unidad_match is not None}")
            if unidad_match:
                print(f"  ID Unidad: {unidad_match.Id_Unidad_Academica}")
            
            # Verificar programa
            programa_match = db.query(Programas).filter(Programas.Nombre_Programa == temp_ejemplo.Nombre_Programa).first()
            print(f"Programa '{temp_ejemplo.Nombre_Programa}' encontrado: {programa_match is not None}")
            if programa_match:
                print(f"  ID Programa: {programa_match.Id_Programa}")
        
        print(f"=================================")
        
        print(f"\n=== PARÁMETROS DEL SP ===")
        print(f"@UUnidad_Academica = '{unidad_sigla}' (tipo: {type(unidad_sigla).__name__})")
        print(f"@SSalones = '{total_grupos}' (tipo: {type(total_grupos).__name__})")
        print(f"@UUsuario = '{usuario_sp}' (tipo: {type(usuario_sp).__name__})")
        print(f"@PPeriodo = '{periodo}' (tipo: {type(periodo).__name__})")
        print(f"@HHost = '{host_sp}' (tipo: {type(host_sp).__name__})")
        print(f"@NNivel = '{nivel}' (tipo: {type(nivel).__name__})")
        print(f"========================")
        
        # Ejecutar el stored procedure (centralizado en el servicio)
        try:
            execute_sp_actualiza_matricula_por_unidad_academica(
                db,
                unidad_sigla=unidad_sigla,
                salones=total_grupos,
                usuario=usuario_sp,
                periodo=periodo,
                host=host_sp,
                nivel=nivel,
            )
            print("SP ejecutado exitosamente")
        except Exception as sp_error:
            print(f"ERROR al ejecutar SP: {sp_error}")
            raise
        
        # Verificar que Temp_Matricula quedó vacía (el SP hace TRUNCATE)
        temp_count_after = db.query(Temp_Matricula).count()
        
        print(f"Registros en Temp_Matricula después: {temp_count_after}")
        print("=== ACTUALIZACIÓN COMPLETADA ===")
        
        return {
            "mensaje": "Matrícula actualizada exitosamente",
            "registros_procesados": temp_count,
            "temp_matricula_limpiada": temp_count_after == 0,
            "usuario": usuario_sp,
            "periodo": periodo,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        db.rollback()
        print(f"ERROR al actualizar matrícula: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error al actualizar la matrícula: {str(e)}")

@router.get("/diagnostico_sp")
async def diagnostico_sp(request: Request, db: Session = Depends(get_db)):
    """
    Endpoint de diagnóstico para analizar por qué no se actualiza la matrícula.
    Simula los JOINs del SP sin hacer cambios.
    """
    try:
        print(f"\n{'='*60}")
        print(f"DIAGNÓSTICO DETALLADO DEL SP")
        print(f"{'='*60}")
        
        # Contar registros en las tablas principales
        temp_count = db.query(Temp_Matricula).count()
        matricula_count = db.query(Matricula).count()
        
        print(f"Registros en Temp_Matricula: {temp_count}")
        print(f"Registros en Matricula: {matricula_count}")
        
        if temp_count == 0:
            return {"error": "No hay datos en Temp_Matricula para diagnosticar"}
        
        # Obtener todos los registros de Temp_Matricula
        temp_records = db.query(Temp_Matricula).all()
        
        diagnostico_resultados = []
        
        for i, tmp in enumerate(temp_records, 1):
            print(f"\n--- DIAGNÓSTICO REGISTRO {i} ---")
            print(f"Temp_Matricula record: {tmp.Periodo}, {tmp.Sigla}, {tmp.Nombre_Programa}")
            
            resultado = {
                'registro': i,
                'temp_data': {
                    'Periodo': tmp.Periodo,
                    'Sigla': tmp.Sigla,
                    'Nombre_Programa': tmp.Nombre_Programa,
                    'Nombre_Rama': tmp.Nombre_Rama,
                    'Nivel': tmp.Nivel,
                    'Modalidad': tmp.Modalidad,
                    'Turno': tmp.Turno,
                    'Semestre': tmp.Semestre,
                    'Grupo_Edad': tmp.Grupo_Edad,
                    'Tipo_Ingreso': tmp.Tipo_Ingreso,
                    'Sexo': tmp.Sexo,
                    'Matricula': tmp.Matricula
                },
                'joins_encontrados': {},
                'joins_faltantes': [],
                'posibles_coincidencias': 0
            }
            
            # Verificar cada JOIN del SP
            
            # 1. Cat_Periodo
            periodo_obj = db.query(Periodo).filter(Periodo.Periodo == tmp.Periodo).first()
            if periodo_obj:
                resultado['joins_encontrados']['Cat_Periodo'] = {
                    'id': periodo_obj.Id_Periodo,
                    'valor': periodo_obj.Periodo
                }
                print(f"✅ Periodo encontrado: ID={periodo_obj.Id_Periodo}")
            else:
                resultado['joins_faltantes'].append('Cat_Periodo')
                print(f"❌ Periodo '{tmp.Periodo}' NO encontrado")
            
            # 2. Cat_Unidad_Academica
            unidad_obj = db.query(Unidad_Academica).filter(Unidad_Academica.Sigla == tmp.Sigla).first()
            if unidad_obj:
                resultado['joins_encontrados']['Cat_Unidad_Academica'] = {
                    'id': unidad_obj.Id_Unidad_Academica,
                    'valor': unidad_obj.Sigla
                }
                print(f"✅ Unidad encontrada: ID={unidad_obj.Id_Unidad_Academica}")
            else:
                resultado['joins_faltantes'].append('Cat_Unidad_Academica')
                print(f"❌ Unidad '{tmp.Sigla}' NO encontrada")
            
            # 3. Cat_Programas
            programa_obj = db.query(Programas).filter(Programas.Nombre_Programa == tmp.Nombre_Programa).first()
            if programa_obj:
                resultado['joins_encontrados']['Cat_Programas'] = {
                    'id': programa_obj.Id_Programa,
                    'valor': programa_obj.Nombre_Programa
                }
                print(f"✅ Programa encontrado: ID={programa_obj.Id_Programa}")
            else:
                resultado['joins_faltantes'].append('Cat_Programas')
                print(f"❌ Programa '{tmp.Nombre_Programa}' NO encontrado")
            
            # Continuar con el resto de JOINs...
            # 4. Cat_Rama
            rama_obj = db.query(Rama).filter(Rama.Nombre_Rama == tmp.Nombre_Rama).first()
            if rama_obj:
                resultado['joins_encontrados']['Cat_Rama'] = {
                    'id': rama_obj.Id_Rama,
                    'valor': rama_obj.Nombre_Rama
                }
                print(f"✅ Rama encontrada: ID={rama_obj.Id_Rama}")
            else:
                resultado['joins_faltantes'].append('Cat_Rama')
                print(f"❌ Rama '{tmp.Nombre_Rama}' NO encontrada")
            
            # Si todos los JOINs principales son exitosos, buscar coincidencias en Matricula
            if all(key in resultado['joins_encontrados'] for key in ['Cat_Periodo', 'Cat_Unidad_Academica', 'Cat_Programas', 'Cat_Rama']):
                # Simular la condición WHERE del SP
                matricula_matches = db.query(Matricula).filter(
                    Matricula.Id_Periodo == resultado['joins_encontrados']['Cat_Periodo']['id'],
                    Matricula.Id_Unidad_Academica == resultado['joins_encontrados']['Cat_Unidad_Academica']['id'],
                    Matricula.Id_Programa == resultado['joins_encontrados']['Cat_Programas']['id'],
                    Matricula.Id_Rama == resultado['joins_encontrados']['Cat_Rama']['id']
                ).count()
                
                resultado['posibles_coincidencias'] = matricula_matches
                print(f"🎯 Coincidencias potenciales en Matricula: {matricula_matches}")
            
            diagnostico_resultados.append(resultado)
        
        print(f"{'='*60}")
        
        return {
            "total_temp_records": temp_count,
            "total_matricula_records": matricula_count,
            "diagnostico_por_registro": diagnostico_resultados,
            "resumen": {
                "registros_con_todos_joins": len([r for r in diagnostico_resultados if not r['joins_faltantes']]),
                "registros_con_coincidencias": len([r for r in diagnostico_resultados if r['posibles_coincidencias'] > 0])
            }
        }
        
    except Exception as e:
        print(f"ERROR en diagnóstico: {str(e)}")
        import traceback
        traceback.print_exc()
        return {"error": str(e)}


@router.post("/limpiar_temp_matricula")
async def limpiar_temp_matricula(db: Session = Depends(get_db)):
    """
    Endpoint temporal para limpiar la tabla Temp_Matricula.
    Útil para testing cuando hay datos con formato incorrecto.
    """
    try:
        count_before = db.query(Temp_Matricula).count()
        db.query(Temp_Matricula).delete()
        db.commit()
        
        return {
            "mensaje": f"Tabla Temp_Matricula limpiada exitosamente",
            "registros_eliminados": count_before
        }
    except Exception as e:
        db.rollback()
        return {"error": f"Error al limpiar Temp_Matricula: {str(e)}"}


@router.post("/preparar_turno")
async def preparar_turno(request: Request, db: Session = Depends(get_db)):
    """
    Endpoint para VALIDAR un turno individual (Fase 1 del nuevo sistema).
    Este endpoint:
    1. Ejecuta SP_Actualiza_Matricula_Por_Unidad_Academica (igual que Guardar Avance)
    2. NO actualiza el semáforo del semestre
    3. Marca el turno como validado para bloqueo permanente
    4. Retorna success=True para que el frontend bloquee los inputs
    
    El SP_Actualiza_Matricula_Por_Semestre_AU se ejecutará automáticamente
    cuando todos los turnos del semestre estén validados.
    """
    try:
        # Obtener datos del request
        data = await request.json()
        
        # Parámetros necesarios
        periodo = data.get('periodo')
        programa = data.get('programa')
        modalidad = data.get('modalidad')
        semestre = data.get('semestre')
        turno = data.get('turno')
        
        # Obtener datos del usuario desde cookies
        id_unidad_academica = int(request.cookies.get("id_unidad_academica", 0))
        id_nivel = int(request.cookies.get("id_nivel", 0))
        nombre_usuario = request.cookies.get("nombre_usuario", "")
        apellidoP_usuario = request.cookies.get("apellidoP_usuario", "")
        apellidoM_usuario = request.cookies.get("apellidoM_usuario", "")
        
        # Construir nombre completo del usuario
        nombre_completo = f"{nombre_usuario} {apellidoP_usuario} {apellidoM_usuario}".strip()
        usuario_sp = nombre_completo or 'sistema'
        
        # Obtener host
        host_sp = get_request_host(request)
        
        print(f"\n{'='*60}")
        print(f"VALIDANDO TURNO INDIVIDUAL - SP POR UNIDAD ACADÉMICA")
        print(f"{'='*60}")
        print(f"Periodo (input): {periodo}")
        print(f"Programa ID: {programa}")
        print(f"Modalidad ID: {modalidad}")
        print(f"Semestre ID: {semestre}")
        print(f"Turno ID: {turno}")
        print(f"Usuario: {usuario_sp}")
        print(f"Host: {host_sp}")
        
        # Validar parámetros obligatorios
        if not all([periodo, programa, modalidad, semestre, turno]):
            return {
                "error": "Faltan parámetros obligatorios",
                "detalles": {
                    "periodo": periodo,
                    "programa": programa,
                    "modalidad": modalidad,
                    "semestre": semestre,
                    "turno": turno
                }
            }
        
        # Convertir período a literal si viene como ID
        if str(periodo).isdigit():
            periodo_obj = db.query(Periodo).filter(Periodo.Id_Periodo == int(periodo)).first()
            periodo_literal = periodo_obj.Periodo if periodo_obj else PERIODO_DEFAULT_LITERAL
            print(f"🔄 Período convertido de ID {periodo} → '{periodo_literal}'")
        else:
            periodo_literal = str(periodo)
            print(f"✅ Período en literal: '{periodo_literal}'")
        
        # Obtener nombres literales desde la BD para el SP
        unidad = db.query(Unidad_Academica).filter(
            Unidad_Academica.Id_Unidad_Academica == id_unidad_academica
        ).first()
        unidad_sigla = unidad.Sigla if unidad else ''
        
        nivel_obj = db.query(Nivel).filter(Nivel.Id_Nivel == id_nivel).first()
        nivel_nombre = nivel_obj.Nivel if nivel_obj else ''
        
        semestre_obj = db.query(Semestre).filter(Semestre.Id_Semestre == int(semestre)).first()
        semestre_nombre = semestre_obj.Semestre if semestre_obj else f"Semestre {semestre}"
        
        turno_obj = db.query(Turno).filter(Turno.Id_Turno == int(turno)).first()
        turno_nombre = turno_obj.Turno if turno_obj else f"Turno {turno}"
        
        print(f"\n📋 Ejecutando SP_Actualiza_Matricula_Por_Unidad_Academica")
        print(f"   Unidad: {unidad_sigla}")
        print(f"   Nivel: {nivel_nombre}")
        print(f"   Período: {periodo_literal}")
        
        # Ejecutar SP de Unidad Académica (igual que Guardar Avance)
        rows_list = execute_sp_actualiza_matricula_por_unidad_academica(
            db,
            unidad_sigla=unidad_sigla,
            salones=0,
            usuario=usuario_sp,
            periodo=periodo_literal,
            host=host_sp,
            nivel=nivel_nombre
        )
        
        print(f"\n✅ SP_Actualiza_Matricula_Por_Unidad_Academica ejecutado exitosamente")
        print(f"📋 Semestre: {semestre_nombre}")
        print(f"🕐 Turno: {turno_nombre}")
        print(f"⏭️  El SP_Actualiza_Matricula_Por_Semestre_AU se ejecutará cuando todos los turnos estén validados")
        
        # Retornar éxito
        return {
            "success": True,
            "mensaje": f"Turno {turno_nombre} del {semestre_nombre} validado exitosamente",
            "turno_validado": turno_nombre,
            "semestre": semestre_nombre,
            "fase": "turno_individual",
            "sp_ejecutado": "SP_Actualiza_Matricula_Por_Unidad_Academica",
            "rows": rows_list,
            "nota": "El turno está bloqueado. El SP final se ejecutará cuando todos los turnos estén completos"
        }
        
    except Exception as e:
        db.rollback()
        print(f"\n❌ ERROR al validar turno: {str(e)}")
        import traceback
        traceback.print_exc()
        
        return {
            "error": f"Error al validar el turno: {str(e)}",
            "success": False
        }


@router.post("/validar_captura_semestre")
async def validar_captura_semestre(request: Request, db: Session = Depends(get_db)):
    """
    Endpoint para validar y finalizar TODOS LOS TURNOS de un semestre (Fase 2 - SP FINAL).
    Este endpoint:
    1. Ejecuta el SP SP_Actualiza_Matricula_Por_Semestre_AU
    2. Actualiza el semáforo del semestre a "Completado" (ID=3)
    3. Registra la acción en bitácora
    4. Devuelve los datos actualizados
    
    SOLO debe llamarse cuando todos los turnos del semestre estén validados.
    """
    try:
        # Obtener datos del request
        data = await request.json()
        
        # Parámetros necesarios
        periodo = data.get('periodo')
        programa = data.get('programa')
        modalidad = data.get('modalidad')
        semestre = data.get('semestre')
        
        # Obtener datos del usuario desde cookies
        id_unidad_academica = int(request.cookies.get("id_unidad_academica", 0))
        id_nivel = int(request.cookies.get("id_nivel", 0))
        nombre_usuario = request.cookies.get("nombre_usuario", "")
        apellidoP_usuario = request.cookies.get("apellidoP_usuario", "")
        apellidoM_usuario = request.cookies.get("apellidoM_usuario", "")
        
        # Construir nombre completo del usuario
        nombre_completo = f"{nombre_usuario} {apellidoP_usuario} {apellidoM_usuario}".strip()
        usuario_sp = nombre_completo or 'sistema'
        
        # Obtener host
        host_sp = get_request_host(request)
        
        print(f"\n{'='*60}")
        print(f"EJECUTANDO SP FINAL - CONSOLIDACIÓN DEL SEMESTRE COMPLETO")
        print(f"{'='*60}")
        print(f"⚠️  TODOS LOS TURNOS DEL SEMESTRE DEBEN ESTAR VALIDADOS")
        print(f"Periodo (input): {periodo}")
        print(f"Programa ID: {programa}")
        print(f"Modalidad ID: {modalidad}")
        print(f"Semestre ID: {semestre}")
        print(f"Usuario: {usuario_sp}")
        print(f"Host: {host_sp}")
        
        # Validar parámetros obligatorios (sin turno)
        if not all([periodo, programa, modalidad, semestre]):
            return {
                "error": "Faltan parámetros obligatorios",
                "detalles": {
                    "periodo": periodo,
                    "programa": programa,
                    "modalidad": modalidad,
                    "semestre": semestre
                }
            }

        # Convertir período a literal si viene como ID (el SP requiere literal ej: '2025-2026/1')
        if str(periodo).isdigit():
            periodo_obj = db.query(Periodo).filter(Periodo.Id_Periodo == int(periodo)).first()
            periodo_literal = periodo_obj.Periodo if periodo_obj else PERIODO_DEFAULT_LITERAL
            print(f"🔄 Período convertido de ID {periodo} → '{periodo_literal}'")
        else:
            periodo_literal = str(periodo)
            print(f"✅ Período en literal: '{periodo_literal}'")
        
        # Obtener nombres literales desde la BD para el SP
        # Unidad Académica
        unidad = db.query(Unidad_Academica).filter(
            Unidad_Academica.Id_Unidad_Academica == id_unidad_academica
        ).first()
        unidad_sigla = unidad.Sigla if unidad else ''
        
        # Programa
        programa_obj = db.query(Programas).filter(
            Programas.Id_Programa == int(programa)
        ).first()
        programa_nombre = programa_obj.Nombre_Programa if programa_obj else ''
        
        # Modalidad
        modalidad_obj = db.query(Modalidad).filter(
            Modalidad.Id_Modalidad == int(modalidad)
        ).first()
        modalidad_nombre = modalidad_obj.Modalidad if modalidad_obj else ''
        
        # Semestre
        semestre_obj = db.query(Semestre).filter(
            Semestre.Id_Semestre == int(semestre)
        ).first()
        semestre_nombre = semestre_obj.Semestre if semestre_obj else ''
        
        # Nivel
        nivel_obj = db.query(Nivel).filter(
            Nivel.Id_Nivel == id_nivel
        ).first()
        nivel_nombre = nivel_obj.Nivel if nivel_obj else ''
        
        print(f"\n📋 Valores literales para el SP:")
        print(f"Unidad Académica: {unidad_sigla}")
        print(f"Programa: {programa_nombre}")
        print(f"Modalidad: {modalidad_nombre}")
        print(f"Semestre: {semestre_nombre}")
        print(f"Nivel: {nivel_nombre}")
        print(f"Período (literal): {periodo_literal}")
        
        # Validar que se obtuvieron todos los valores
        if not all([unidad_sigla, programa_nombre, modalidad_nombre, semestre_nombre, nivel_nombre]):
            return {
                "error": "No se pudieron obtener los nombres literales de los catálogos",
                "detalles": {
                    "unidad": unidad_sigla,
                    "programa": programa_nombre,
                    "modalidad": modalidad_nombre,
                    "semestre": semestre_nombre,
                    "nivel": nivel_nombre
                }
            }
        
        # Ejecutar el SP SP_Actualiza_Matricula_Por_Semestre_AU
        # Nota: El SP requiere @SSalones, lo obtenemos del request (Total Grupos)
        total_grupos = int(data.get('total_grupos', 0) or 0)
        print(f"Total de Grupos (salones) para validación: {total_grupos}")
        # Ejecutar SP de validación por semestre
        rows_list = execute_sp_actualiza_matricula_por_semestre_au(
            db,
            unidad_sigla=unidad_sigla,
            programa_nombre=programa_nombre,
            modalidad_nombre=modalidad_nombre,
            semestre_nombre=semestre_nombre,
            salones=total_grupos,
            usuario=usuario_sp,
            periodo=periodo_literal,
            host=host_sp,
            nivel=nivel_nombre,
        )
        
        print(f"\n✅ SP ejecutado exitosamente")
        print(f"Filas finales devueltas: {len(rows_list)}")
        
        # Verificar semáforo sin SQL crudo: reconsultar SP y extraer estado
        print(f"\n🔍 Consultando estado actualizado del semáforo vía SP...")
        estado_semaforo_actualizado = get_estado_semaforo_desde_sp(
            db,
            id_unidad_academica=id_unidad_academica,
            id_nivel=id_nivel,
            periodo_input=periodo_literal,
            usuario=usuario_sp,
            host=host_sp,
            programa_nombre=programa_nombre,
            modalidad_nombre=modalidad_nombre,
            semestre_nombre=semestre_nombre,
        )
        
        return {
            "success": True,
            "mensaje": f"SP FINAL ejecutado - {semestre_nombre} consolidado completamente",
            "rows": rows_list,
            "semestre_validado": semestre_nombre,
            "estado_semaforo": estado_semaforo_actualizado,
            "fase": "sp_final_consolidado",
            "debug": {
                "sp_ejecutado": "SP_Actualiza_Matricula_Por_Semestre_AU",
                "parametros": {
                    "unidad": unidad_sigla,
                    "programa": programa_nombre,
                    "modalidad": modalidad_nombre,
                    "semestre": semestre_nombre,
                    "salones": total_grupos,
                    "usuario": usuario_sp,
                    "periodo": periodo_literal,
                    "host": host_sp,
                    "nivel": nivel_nombre
                }
            }
        }
        
    except Exception as e:
        db.rollback()
        print(f"\n❌ ERROR al validar captura: {str(e)}")
        import traceback
        traceback.print_exc()
        
        return {
            "error": f"Error al validar la captura del semestre: {str(e)}",
            "success": False
        }


@router.post("/validar_semestre_rol")
async def validar_semestre_rol(request: Request, db: Session = Depends(get_db)):
    """
    Endpoint para que roles de validación (ID 4 y 5) aprueben un semestre completo.
    Marca el semestre como validado y lo bloquea para futuras modificaciones.
    """
    try:
        # Obtener datos del usuario desde cookies
        usuario = request.cookies.get("usuario", "")
        id_usuario = int(request.cookies.get("id_usuario", 0))
        id_rol = int(request.cookies.get("id_rol", 0))
        
        # Validar que sea un rol de validación
        if id_rol not in [4, 5]:
            return {
                "success": False,
                "error": "Solo los roles de validación pueden usar esta función"
            }
        
        # Obtener datos del request
        body = await request.json()
        periodo_id = body.get("periodo")
        programa_id = body.get("programa")
        modalidad_id = body.get("modalidad")
        semestre_id = body.get("semestre")
        
        print(f"\n✅ Validación de semestre por rol {id_rol} - Usuario: {usuario}")
        print(f"   Periodo: {periodo_id}, Programa: {programa_id}, Modalidad: {modalidad_id}, Semestre: {semestre_id}")
        
        # Aquí se implementará la lógica de validación
        # Por ahora, retornamos éxito
        
        return {
            "success": True,
            "mensaje": f"Semestre validado exitosamente por {usuario}",
            "data": {
                "validado_por": usuario,
                "id_usuario": id_usuario,
                "id_rol": id_rol,
                "fecha_validacion": datetime.now().isoformat()
            }
        }
        
    except Exception as e:
        print(f"\n❌ ERROR al validar semestre (rol): {str(e)}")
        import traceback
        traceback.print_exc()
        
        return {
            "success": False,
            "error": f"Error al validar el semestre: {str(e)}"
        }


@router.post("/rechazar_semestre_rol")
async def rechazar_semestre_rol(request: Request, db: Session = Depends(get_db)):
    """
    Endpoint para que roles de validación (ID 4 y 5) rechacen un semestre.
    Devuelve el semestre al capturista para correcciones.
    """
    try:
        # Obtener datos del usuario desde cookies
        usuario = request.cookies.get("usuario", "")
        id_usuario = int(request.cookies.get("id_usuario", 0))
        id_rol = int(request.cookies.get("id_rol", 0))
        
        # Validar que sea un rol de validación
        if id_rol not in [4, 5]:
            return {
                "success": False,
                "error": "Solo los roles de validación pueden usar esta función"
            }
        
        # Obtener datos del request
        body = await request.json()
        periodo_id = body.get("periodo")
        programa_id = body.get("programa")
        modalidad_id = body.get("modalidad")
        semestre_id = body.get("semestre")
        motivo = body.get("motivo", "").strip()
        
        if not motivo:
            return {
                "success": False,
                "error": "El motivo del rechazo es obligatorio"
            }
        
        print(f"\n❌ Rechazo de semestre por rol {id_rol} - Usuario: {usuario}")
        print(f"   Periodo: {periodo_id}, Programa: {programa_id}, Modalidad: {modalidad_id}, Semestre: {semestre_id}")
        print(f"   Motivo: {motivo}")
        
        # Aquí se implementará la lógica de rechazo
        # Por ahora, retornamos éxito
        
        return {
            "success": True,
            "mensaje": f"Semestre rechazado por {usuario}",
            "data": {
                "rechazado_por": usuario,
                "id_usuario": id_usuario,
                "id_rol": id_rol,
                "motivo": motivo,
                "fecha_rechazo": datetime.now().isoformat()
            }
        }
        
    except Exception as e:
        print(f"\n❌ ERROR al rechazar semestre (rol): {str(e)}")
        import traceback
        traceback.print_exc()
        
        return {
            "success": False,
            "error": f"Error al rechazar el semestre: {str(e)}"
        }
