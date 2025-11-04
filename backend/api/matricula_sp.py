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
    get_matricula_metadata_from_sp
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
    Endpoint principal para la captura de matrícula usando EXCLUSIVAMENTE Stored Procedures.
    Solo accesible para usuarios con rol 'Capturista'.
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

    # Validar que el usuario tenga el rol de 'Capturista'
    if nombre_rol.lower() != 'capturista':
        return templates.TemplateResponse("error.html", {
            "request": request,
            "error_message": "Acceso denegado: Solo los usuarios con rol 'Capturista' pueden acceder a esta funcionalidad.",
            "redirect_url": "/mod_principal/"
        })

    print(f"\n{'='*60}")
    print(f"CARGANDO VISTA DE MATRÍCULA - TODO DESDE SP")
    print(f"Usuario: {nombre_completo}")
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
    """Endpoint temporal para ver qué trae el SP exactamente — detecta UA y nivel desde cookies."""
    try:
        print(f"\n{'='*60}")
        print(f"EJECUTANDO SP (debug) usando cookies del usuario")
        print(f"{'='*60}")

        # Leer cookies del usuario
        id_unidad_academica = int(request.cookies.get("id_unidad_academica", 0))
        id_nivel = int(request.cookies.get("id_nivel", 0))
        nombre_usuario = request.cookies.get("nombre_usuario", "")
        apellidoP_usuario = request.cookies.get("apellidoP_usuario", "")
        apellidoM_usuario = request.cookies.get("apellidoM_usuario", "")
        nombre_completo = " ".join(filter(None, [nombre_usuario, apellidoP_usuario, apellidoM_usuario]))
        periodo = '2025-2026/1'
    

        print(f"ID Unidad Académica (cookie): {id_unidad_academica}")
        print(f"ID Nivel (cookie): {id_nivel}")
        print(f"Usuario: {nombre_completo}")
        print(f"Periodo (forzado): {periodo}")

        # Obtener usuario y host para el SP
        usuario_sp = nombre_completo or 'sistema'
        host_sp = get_request_host(request)
        print(f"Host: {host_sp}")

        unidad = db.query(Unidad_Academica).filter(Unidad_Academica.Id_Unidad_Academica == id_unidad_academica).first()
        nivel = db.query(Nivel).filter(Nivel.Id_Nivel == id_nivel).first()
        periodo_obj = db.query(Periodo).filter(Periodo.Periodo == periodo).first()

        if not unidad:
            return {"error": f"Unidad Académica con id {id_unidad_academica} no encontrada"}
        if not nivel:
            return {"error": f"Nivel con id {id_nivel} no encontrado"}

        unidad_sigla = unidad.Sigla
        nivel_nombre = nivel.Nivel
        periodo_nombre = periodo_obj.Periodo if periodo_obj else periodo

        print(f"Ejecutando SP con: Unidad={unidad_sigla}, Periodo={periodo_nombre}, Nivel={nivel_nombre}, Usuario={usuario_sp}, Host={host_sp}")

        sql = text("""
            EXEC SP_Consulta_Matricula_Unidad_Academica 
                @UUnidad_Academica = :unidad, 
                @Pperiodo = :periodo, 
                @NNivel = :nivel, 
                @UUsuario = :usuario, 
                @HHost = :host
        """)
        result = db.execute(sql, {
            'unidad': unidad_sigla, 
            'periodo': periodo_nombre, 
            'nivel': nivel_nombre,
            'usuario': usuario_sp,
            'host': host_sp
        })
        rows = result.fetchall()

        print(f"TOTAL DE FILAS DEVUELTAS: {len(rows)}")

        columns = []
        if rows:
            # Analizar el tipo de resultado
            print(f"\nTIPO DE RESULTADO: {type(rows[0])}")
            print(f"PRIMERA FILA RAW: {rows[0]}")

            # Intentar obtener nombres de columnas de diferentes maneras
            try:
                columns = list(rows[0].keys())
                print(f"\nCOLUMNAS DISPONIBLES (método keys) - {len(columns)}:")
                for i, col in enumerate(columns, 1):
                    print(f"  {i:2d}. {col}")
            except Exception as e1:
                print(f"Error con método keys(): {e1}")
                try:
                    columns = list(rows[0]._fields)
                    print(f"\nCOLUMNAS DISPONIBLES (método _fields) - {len(columns)}:")
                    for i, col in enumerate(columns, 1):
                        print(f"  {i:2d}. {col}")
                except Exception as e2:
                    print(f"Error con método _fields: {e2}")
                    attrs = [attr for attr in dir(rows[0]) if not attr.startswith('_')]
                    print(f"MÉTODOS/ATRIBUTOS DISPONIBLES: {attrs}")
                    columns = []

            # Mostrar primera fila completa
            print(f"\nPRIMERA FILA DE DATOS:")
            if columns:
                for col in columns:
                    try:
                        value = getattr(rows[0], col, 'N/A')
                        print(f"  {col}: '{value}' ({type(value).__name__})")
                    except Exception as e:
                        print(f"  {col}: ERROR - {e}")
            else:
                print(f"  No se pudieron obtener columnas, fila raw: {rows[0]}")

            # Mostrar todas las filas (máximo 20 para no saturar)
            print(f"\nTODAS LAS FILAS (máximo 20):")
            for i, row in enumerate(rows[:20], 1):
                print(f"\nFila {i}:")
                if columns:
                    for col in columns:
                        try:
                            value = getattr(row, col, 'N/A')
                            print(f"  {col}: {value}")
                        except Exception as e:
                            print(f"  {col}: ERROR - {e}")
                else:
                    print(f"  Fila raw: {row}")
                print("-" * 40)

            if len(rows) > 20:
                print(f"\n... y {len(rows) - 20} filas más")

            # Análisis de valores únicos por columna
            if columns:
                print(f"\nANÁLISIS DE VALORES ÚNICOS POR COLUMNA:")
                for col in columns:
                    try:
                        unique_values = set()
                        for row in rows:
                            try:
                                value = getattr(row, col, None)
                                if value is not None:
                                    unique_values.add(str(value))
                            except Exception:
                                continue

                        print(f"\n{col}:")
                        if len(unique_values) <= 10:
                            for val in sorted(unique_values):
                                print(f"  - '{val}'")
                        else:
                            sorted_vals = sorted(unique_values)
                            print(f"  Primeros 10 valores de {len(unique_values)} únicos:")
                            for val in sorted_vals[:10]:
                                print(f"  - '{val}'")
                            print(f"  ... y {len(unique_values) - 10} más")
                    except Exception as e:
                        print(f"\nError analizando columna {col}: {e}")
        else:
            print("EL SP NO DEVOLVIÓ DATOS")

        print(f"{'='*60}")

        return {
            "mensaje": f"SP ejecutado - {len(rows)} filas devueltas",
            "total_filas": len(rows),
            "columnas": columns,
            "primera_fila": str(rows[0]) if rows else None
        }

    except Exception as e:
        print(f"ERROR AL EJECUTAR SP: {str(e)}")
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
        print(f"@SSalones = '{total_grupos}' (tipo: {type(total_grupos).__name__})")
        print(f"@UUsuario = '{usuario_sp}' (tipo: {type(usuario_sp).__name__})")
        print(f"@PPeriodo = '{periodo}' (tipo: {type(periodo).__name__})")
        print(f"@HHost = '{host_sp}' (tipo: {type(host_sp).__name__})")
        print(f"@NNivel = '{nivel}' (tipo: {type(nivel).__name__})")
        print(f"========================")
        
        # Ejecutar el stored procedure
        try:
            cursor = db.execute(text("""
                EXEC [dbo].[SP_Actualiza_Matricula_Por_Unidad_Academica] 
                    @SSalones = :salones,
                    @UUsuario = :usuario,
                    @PPeriodo = :periodo,
                    @HHost = :host,
                    @NNivel = :nivel
            """), {
                'salones': total_grupos,
                'usuario': usuario_sp,
                'periodo': periodo,
                'host': host_sp,
                'nivel': nivel
            })
            
            # Intentar obtener resultados del SP (mensajes, errores, etc.)
            try:
                result = cursor.fetchall()
                if result:
                    print(f"Resultado del SP: {result}")
            except Exception as e:
                print(f"No hay resultados del SP (normal): {e}")
            
            db.commit()
            print("SP ejecutado exitosamente")
            
        except Exception as sp_error:
            print(f"ERROR al ejecutar SP: {sp_error}")
            db.rollback()
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


@router.post("/validar_captura_semestre")
async def validar_captura_semestre(request: Request, db: Session = Depends(get_db)):
    """
    Endpoint para validar y finalizar la captura de un semestre específico.
    Ejecuta el SP SP_Actualiza_Matricula_Por_Semestre_AU que:
    1. Actualiza la matrícula completa
    2. Cambia el semáforo del semestre a "Completado" (ID=3)
    3. Registra la acción en bitácora
    4. Devuelve los datos actualizados
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
        print(f"VALIDANDO CAPTURA DE SEMESTRE")
        print(f"{'='*60}")
        print(f"Periodo: {periodo}")
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
        sp_query = text("""
            EXEC [dbo].[SP_Actualiza_Matricula_Por_Semestre_AU]
                @UUnidad_Academica = :unidad_academica,
                @PPrograma = :programa,
                @MModalidad = :modalidad,
                @SSemestre = :semestre,
                @UUsuario = :usuario,
                @PPeriodo = :periodo,
                @HHost = :host,
                @NNivel = :nivel
        """)
        
        result = db.execute(sp_query, {
            'unidad_academica': unidad_sigla,
            'programa': programa_nombre,
            'modalidad': modalidad_nombre,
            'semestre': semestre_nombre,
            'usuario': usuario_sp,
            'periodo': periodo,
            'host': host_sp,
            'nivel': nivel_nombre
        })
        
        db.commit()
        
        # El SP devuelve múltiples result sets, necesitamos el último (datos actualizados)
        # Consumir todos los result sets intermedios
        rows_list = []
        columns = []
        
        try:
            # Iterar sobre todos los result sets
            while True:
                # Intentar obtener las filas del result set actual
                try:
                    rows_raw = result.fetchall()
                    if rows_raw:
                        columns = result.keys()
                        # Guardar las filas del último result set con datos
                        rows_list = []
                        for row in rows_raw:
                            row_dict = {}
                            for i, col in enumerate(columns):
                                val = row[i]
                                # Convertir tipos especiales
                                if isinstance(val, datetime):
                                    val = val.isoformat()
                                elif val is None:
                                    val = None
                                row_dict[col] = val
                            rows_list.append(row_dict)
                        print(f"📦 Result set procesado: {len(rows_list)} filas")
                except Exception as fetch_error:
                    print(f"⚠️ Error al procesar result set: {fetch_error}")
                    break
                
                # Intentar avanzar al siguiente result set
                if not result.nextset():
                    break
        except Exception as e:
            print(f"⚠️ Fin de result sets: {e}")
        
        print(f"\n✅ SP ejecutado exitosamente")
        print(f"Filas finales devueltas: {len(rows_list)}")
        
        # Consultar directamente el estado del semáforo actualizado desde la tabla
        # porque el SP de consulta puede no incluir semestres completados
        print(f"\n🔍 Consultando estado actualizado del semáforo para verificar...")
        
        try:
            query_semaforo = text("""
                SELECT ssua.Id_Semestre, ssua.id_semaforo, sem.Semestre
                FROM [dbo].[Semaforo_Semestre_Unidad_Academica] ssua
                INNER JOIN [dbo].[Cat_Periodo] per ON ssua.Id_Periodo = per.Id_Periodo
                INNER JOIN [dbo].[Cat_Unidad_Academica] ua ON ssua.Id_Unidad_Academica = ua.Id_Unidad_Academica
                INNER JOIN [dbo].[Programa_Modalidad] pm ON pm.id_Modalidad_programa = ssua.id_Modalidad_programa
                INNER JOIN [dbo].[Cat_Modalidad] md ON md.Id_modalidad = pm.Id_modalidad
                INNER JOIN [dbo].[Cat_Programas] pro ON pm.Id_Programa = pro.Id_Programa
                INNER JOIN [dbo].[Cat_Semestre] sem ON ssua.Id_Semestre = sem.Id_Semestre
                WHERE per.Periodo = :periodo
                    AND ua.sigla = :unidad
                    AND md.Modalidad = :modalidad
                    AND pro.Nombre_Programa = :programa
                    AND sem.Semestre = :semestre
            """)
            
            result_semaforo = db.execute(query_semaforo, {
                'periodo': periodo,
                'unidad': unidad_sigla,
                'modalidad': modalidad_nombre,
                'programa': programa_nombre,
                'semestre': semestre_nombre
            })
            
            semaforo_row = result_semaforo.fetchone()
            estado_semaforo_actualizado = None
            
            if semaforo_row:
                estado_semaforo_actualizado = semaforo_row[1]  # id_semaforo
                print(f"✅ Estado del semáforo verificado: ID={estado_semaforo_actualizado}")
                
                if estado_semaforo_actualizado == 3:
                    print(f"🟢 Semestre '{semestre_nombre}' marcado como COMPLETADO")
                else:
                    print(f"⚠️ ADVERTENCIA: Semestre '{semestre_nombre}' tiene estado {estado_semaforo_actualizado}, se esperaba 3")
            else:
                print(f"⚠️ No se encontró registro de semáforo para {semestre_nombre}")
                
        except Exception as e_semaforo:
            print(f"⚠️ Error al consultar semáforo: {e_semaforo}")
            estado_semaforo_actualizado = None
        
        return {
            "success": True,
            "mensaje": f"Captura del {semestre_nombre} validada y completada exitosamente",
            "rows": rows_list,
            "semestre_validado": semestre_nombre,
            "estado_semaforo": estado_semaforo_actualizado,
            "debug": {
                "sp_ejecutado": "SP_Actualiza_Matricula_Por_Semestre_AU",
                "parametros": {
                    "unidad": unidad_sigla,
                    "programa": programa_nombre,
                    "modalidad": modalidad_nombre,
                    "semestre": semestre_nombre,
                    "usuario": usuario_sp,
                    "periodo": periodo,
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


