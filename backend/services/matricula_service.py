"""Servicio para operaciones de matrícula usando EXCLUSIVAMENTE Stored Procedures."""

from backend.crud.Matricula import (
    execute_sp_consulta_matricula,
    resolve_periodo_by_id_or_literal,
    get_unidad_and_nivel_info,
)

from sqlalchemy.orm import Session
from typing import Dict, List, Any, Optional, Tuple
from sqlalchemy import text
from datetime import datetime


def extract_unique_values_from_sp(rows_list: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Extraer valores únicos del SP para grupos de edad, tipos de ingreso, etc.
    Como el SP NO devuelve IDs, usamos los labels directamente.
    
    Args:
        rows_list: Lista de filas del SP como diccionarios
        
    Returns:
        Dict con estructuras únicas extraídas del SP
    """
    grupos_edad_set = set()
    tipos_ingreso_set = set()
    programas_set = set()
    modalidades_set = set()
    semestres_set = set()
    turnos_set = set()
    
    for row in rows_list:
        # Extraer valores únicos como strings
        if 'Grupo_Edad' in row and row['Grupo_Edad']:
            grupos_edad_set.add(str(row['Grupo_Edad']))
        
        if 'Tipo_de_Ingreso' in row and row['Tipo_de_Ingreso']:
            tipos_ingreso_set.add(str(row['Tipo_de_Ingreso']))
        
        if 'Nombre_Programa' in row and row['Nombre_Programa']:
            programas_set.add(str(row['Nombre_Programa']))
        
        if 'Modalidad' in row and row['Modalidad']:
            modalidades_set.add(str(row['Modalidad']))
        
        if 'Semestre' in row and row['Semestre']:
            semestres_set.add(str(row['Semestre']))
        
        if 'Turno' in row and row['Turno']:
            turnos_set.add(str(row['Turno']))
    
    # Convertir a listas ordenadas (sin IDs, solo labels)
    return {
        'grupos_edad': sorted(list(grupos_edad_set)),
        'tipos_ingreso': sorted(list(tipos_ingreso_set)),
        'programas': sorted(list(programas_set)),
        'modalidades': sorted(list(modalidades_set)),
        'semestres': sorted(list(semestres_set)),
        'turnos': sorted(list(turnos_set))
    }


def get_matricula_metadata_from_sp(
    db: Session,
    id_unidad_academica: int,
    id_nivel: int,
    periodo_input: Optional[str] = None,
    default_periodo: str = "2025-2026/1",
    usuario: str = 'sistema',
    host: str = 'localhost'
) -> Dict[str, Any]:
    """
    Obtener TODOS los metadatos necesarios para la captura de matrícula EXCLUSIVAMENTE del SP.
    
    Args:
        db: Sesión de base de datos
        id_unidad_academica: ID de la unidad académica
        id_nivel: ID del nivel educativo
        periodo_input: Periodo como ID o literal (opcional)
        default_periodo: Periodo por defecto
        usuario: Nombre del usuario que ejecuta la consulta
        host: Host desde donde se realiza la petición
    
    Returns:
        Dict con grupos_edad, tipos_ingreso, programas, modalidades, semestres, turnos
    """
    try:
        # Resolver información de unidad y nivel
        unidad_sigla, nivel_nombre = get_unidad_and_nivel_info(db, id_unidad_academica, id_nivel)
        
        if not unidad_sigla or not nivel_nombre:
            return {
                'error': 'No se pudo resolver unidad académica o nivel',
                'grupos_edad': [],
                'tipos_ingreso': [],
                'programas': [],
                'modalidades': [],
                'semestres': [],
                'turnos': []
            }
        
        # Resolver periodo
        periodo_nombre = resolve_periodo_by_id_or_literal(db, periodo_input or default_periodo, default_periodo)
        
        # Ejecutar SP con parámetros de usuario y host
        rows_list, columns = execute_sp_consulta_matricula(
            db, 
            unidad_sigla, 
            periodo_nombre, 
            nivel_nombre,
            usuario,
            host
        )
        
        print(f"\n=== EXTRAYENDO METADATOS DEL SP ===")
        print(f"Total de filas obtenidas: {len(rows_list)}")
        print(f"Columnas disponibles: {columns}")
        
        if not rows_list:
            print("⚠️ El SP no devolvió datos")
            return {
                'error': 'El SP no devolvió datos',
                'grupos_edad': [],
                'tipos_ingreso': [],
                'programas': [],
                'modalidades': [],
                'semestres': [],
                'turnos': []
            }
        
        # Extraer valores únicos del SP
        metadata = extract_unique_values_from_sp(rows_list)
        
        print(f"\n=== METADATOS EXTRAÍDOS ===")
        print(f"Grupos de Edad: {len(metadata['grupos_edad'])} -> {metadata['grupos_edad']}")
        print(f"Tipos de Ingreso: {len(metadata['tipos_ingreso'])} -> {metadata['tipos_ingreso']}")
        print(f"Programas: {len(metadata['programas'])} -> {metadata['programas']}")
        print(f"Modalidades: {len(metadata['modalidades'])} -> {metadata['modalidades']}")
        print(f"Semestres: {len(metadata['semestres'])} -> {metadata['semestres']}")
        print(f"Turnos: {len(metadata['turnos'])} -> {metadata['turnos']}")
        
        return metadata
        
    except Exception as e:
        error_msg = f"Error al obtener metadatos del SP: {str(e)}"
        print(error_msg)
        return {
            'error': error_msg,
            'grupos_edad': [],
            'tipos_ingreso': [],
            'programas': [],
            'modalidades': [],
            'semestres': [],
            'turnos': []
        }


def execute_matricula_sp_with_context(
    db: Session,
    id_unidad_academica: int,
    id_nivel: int,
    periodo_input: Optional[str] = None,
    default_periodo: str = "2025-2026/1",
    usuario: str = 'sistema',
    host: str = 'localhost'
) -> Tuple[List[Dict[str, Any]], Dict[str, Any], str]:
    """
    Ejecutar SP de matrícula con contexto de usuario y devolver datos normalizados.
    SOLO filtra por estatus activo, NO procesa ni agrega datos.
    
    Args:
        db: Sesión de base de datos
        id_unidad_academica: ID de la unidad académica del usuario
        id_nivel: ID del nivel del usuario
        periodo_input: Periodo como ID o literal (opcional)
        default_periodo: Periodo por defecto
        usuario: Nombre del usuario que ejecuta la consulta
        host: Host desde donde se realiza la petición
        
    Returns:
        Tuple[List[Dict], Dict[str, Any], str]: (filas_sp_activas, metadatos_extraídos, mensaje_debug)
    """
    try:
        # Resolver información de unidad y nivel
        unidad_sigla, nivel_nombre = get_unidad_and_nivel_info(db, id_unidad_academica, id_nivel)
        
        if not unidad_sigla:
            return [], {}, f"Error: Unidad Académica con id {id_unidad_academica} no encontrada"
        if not nivel_nombre:
            return [], {}, f"Error: Nivel con id {id_nivel} no encontrado"
            
        # Resolver periodo
        periodo_nombre = resolve_periodo_by_id_or_literal(db, periodo_input or default_periodo, default_periodo)
        
        print(f"\n=== EJECUTANDO SP ===")
        print(f"Unidad: {unidad_sigla}, Periodo: {periodo_nombre}, Nivel: {nivel_nombre}")
        print(f"Usuario: {usuario}, Host: {host}")
        
        # Ejecutar SP con parámetros de usuario y host
        rows_list, columns = execute_sp_consulta_matricula(
            db, 
            unidad_sigla, 
            periodo_nombre, 
            nivel_nombre,
            usuario,
            host
        )
        
        # Log detallado de las filas obtenidas del SP
        print(f"\n=== DEBUG: FILAS OBTENIDAS DEL SP ===")
        print(f"Total de filas: {len(rows_list)}")
        if rows_list:
            print(f"Columnas disponibles: {list(rows_list[0].keys())}")
            for i, row in enumerate(rows_list[:3]):
                print(f"Fila {i+1}: {row}")
        else:
            print("⚠️ No se obtuvieron filas del SP.")
        
        # Manejar valores NULL - convertir a cadena vacía
        rows_processed = []
        for row in rows_list:
            processed_row = {}
            for key, value in row.items():
                # Si el valor es NULL o None, convertirlo a cadena vacía
                if value is None or (isinstance(value, str) and value.upper() == 'NULL'):
                    processed_row[key] = ""
                else:
                    processed_row[key] = value
            rows_processed.append(processed_row)
        
        # Extraer metadatos del SP
        metadata = extract_unique_values_from_sp(rows_processed)
        
        # Log de valores únicos detectados por columna
        print("\n=== ANÁLISIS DE VALORES ÚNICOS POR COLUMNA ===")
        if rows_processed:
            for col in rows_processed[0].keys():
                unique_values = set()
                for row in rows_processed:
                    if row[col] is not None and row[col] != "":
                        unique_values.add(str(row[col]))
                print(f"Columna '{col}': {len(unique_values)} valores únicos -> {sorted(list(unique_values))[:10]}")
        
        debug_msg = f"SP ejecutado correctamente, {len(rows_processed)} filas. Unidad: {unidad_sigla}, Periodo: {periodo_nombre}, Nivel: {nivel_nombre}"
        
        return rows_processed, metadata, debug_msg
        
    except Exception as e:
        error_msg = f"Error al ejecutar SP de matrícula: {str(e)}"
        print(error_msg)
        import traceback
        traceback.print_exc()
        return [], {}, error_msg


# =============================
# SP helpers (centralizar SQL)
# =============================

def execute_sp_actualiza_matricula_por_unidad_academica(
    db: Session,
    unidad_sigla: str,
    salones: int,
    usuario: str,
    periodo: str,
    host: str,
    nivel: str,
) -> None:
    """Ejecuta SP_Actualiza_Matricula_Por_Unidad_Academica. Centraliza SQL crudo aquí."""
    sql = text(
        """
        EXEC [dbo].[SP_Actualiza_Matricula_Por_Unidad_Academica]
            @UUnidad_Academica = :unidad_sigla,
            @SSalones = :salones,
            @UUsuario = :usuario,
            @PPeriodo = :periodo,
            @HHost   = :host,
            @NNivel  = :nivel
        """
    )
    db.execute(sql, {
        'unidad_sigla': unidad_sigla,
        'salones': salones,
        'usuario': usuario,
        'periodo': periodo,
        'host': host,
        'nivel': nivel,
    })
    db.commit()


def execute_sp_actualiza_matricula_por_semestre_au(
    db: Session,
    unidad_sigla: str,
    programa_nombre: str,
    modalidad_nombre: str,
    semestre_nombre: str,
    salones: int,
    usuario: str,
    periodo: str,
    host: str,
    nivel: str,
) -> List[Dict[str, Any]]:
    """Ejecuta SP_Actualiza_Matricula_Por_Semestre_AU y devuelve el último result set como lista de dicts."""
    sql = text(
        """
        EXEC [dbo].[SP_Actualiza_Matricula_Por_Semestre_AU]
            @UUnidad_Academica = :unidad,
            @PPrograma = :programa,
            @MModalidad = :modalidad,
            @SSemestre = :semestre,
            @SSalones = :salones,
            @UUsuario = :usuario,
            @PPeriodo = :periodo,
            @HHost = :host,
            @NNivel = :nivel
        """
    )
    result = db.execute(sql, {
        'unidad': unidad_sigla,
        'programa': programa_nombre,
        'modalidad': modalidad_nombre,
        'semestre': semestre_nombre,
        'salones': int(salones) if salones is not None else 0,
        'usuario': usuario,
        'periodo': periodo,
        'host': host,
        'nivel': nivel,
    })
    db.commit()

    # Intentar extraer el último result set con filas
    rows_list: List[Dict[str, Any]] = []
    try:
        raw_cursor = getattr(result, 'cursor', None)
        if raw_cursor is not None and hasattr(raw_cursor, 'nextset'):
            while True:
                try:
                    rows_raw = raw_cursor.fetchall()
                except Exception:
                    rows_raw = []
                if rows_raw:
                    cols = [d[0] for d in (raw_cursor.description or [])]
                    rows_list = []
                    for row in rows_raw:
                        rd = {}
                        for i, c in enumerate(cols):
                            try:
                                v = row[i]
                            except Exception:
                                v = None
                            if isinstance(v, (bytes, bytearray)):
                                try:
                                    v = v.decode('utf-8', errors='ignore')
                                except Exception:
                                    v = str(v)
                            if isinstance(v, datetime):
                                v = v.isoformat()
                            rd[c] = v
                        rows_list.append(rd)
                if not raw_cursor.nextset():
                    break
        else:
            try:
                rows_raw = result.fetchall()
                cols = list(result.keys())
            except Exception:
                rows_raw = []
                cols = []
            for row in rows_raw:
                rd = {}
                for i, c in enumerate(cols):
                    v = row[i]
                    if isinstance(v, datetime):
                        v = v.isoformat()
                    rd[c] = v
                rows_list.append(rd)
    except Exception:
        pass

    return rows_list


def get_estado_semaforo_desde_sp(
    db: Session,
    id_unidad_academica: int,
    id_nivel: int,
    periodo_input: str,
    usuario: str,
    host: str,
    programa_nombre: str,
    modalidad_nombre: str,
    semestre_nombre: str,
) -> Optional[int]:
    """Consulta el SP de matrícula y devuelve el Id_Semaforo para el contexto solicitado."""
    rows, _meta, _dbg = execute_matricula_sp_with_context(
        db,
        id_unidad_academica,
        id_nivel,
        periodo_input,
        periodo_input,
        usuario,
        host,
    )
    # Filtrar por programa, modalidad y semestre
    for r in rows:
        if (
            str(r.get('Nombre_Programa','')) == str(programa_nombre)
            and str(r.get('Modalidad','')) == str(modalidad_nombre)
            and str(r.get('Semestre','')) == str(semestre_nombre)
        ):
            # soportar variantes de nombre de columna
            for k in ('Id_Semaforo','id_semaforo','ID_Semaforo'):
                if k in r and r[k] not in (None, ''):
                    try:
                        return int(r[k])
                    except Exception:
                        continue
    return None


def execute_sp_finaliza_captura_matricula(
    db: Session,
    unidad_sigla: str,
    programa_nombre: str,
    modalidad_nombre: str,
    semestre_nombre: str,
    salones: int,
    usuario: str,
    periodo: str,
    host: str,
    nivel: str,
) -> None:
    """
    Ejecuta SP_Finaliza_Captura_Matricula.
    Este SP se ejecuta automáticamente después de SP_Actualiza_Matricula_Por_Semestre_AU
    para finalizar completamente la captura del semestre.
    """
    sql = text(
        """
        EXEC [dbo].[SP_Finaliza_Captura_Matricula]
            @UUnidad_Academica = :unidad,
            @PPrograma = :programa,
            @MModalidad = :modalidad,
            @SSemestre = :semestre,
            @SSalones = :salones,
            @UUsuario = :usuario,
            @PPeriodo = :periodo,
            @HHost = :host,
            @NNivel = :nivel
        """
    )
    
    try:
        db.execute(sql, {
            'unidad': unidad_sigla,
            'programa': programa_nombre,
            'modalidad': modalidad_nombre,
            'semestre': semestre_nombre,
            'salones': int(salones) if salones is not None else 0,
            'usuario': usuario,
            'periodo': periodo,
            'host': host,
            'nivel': nivel,
        })
        db.commit()
        print(f"✅ SP_Finaliza_Captura_Matricula ejecutado exitosamente")
    except Exception as e:
        print(f"❌ Error al ejecutar SP_Finaliza_Captura_Matricula: {str(e)}")
        db.rollback()
        raise


def execute_sp_valida_matricula(
    db: Session,
    periodo: str,
    unidad_sigla: str,
    usuario: str,
    host: str,
    semaforo: int,
    nota: str = ""
) -> None:
    """
    Ejecuta SP_Valida_Matricula.
    Este SP se ejecuta cuando un rol de validación (4 o 5) aprueba la matrícula.
    """
    sql = text(
        """
        EXEC [dbo].[SP_Valida_Matricula]
            @PPeriodo = :periodo,
            @UUnidad_Academica = :unidad,
            @UUsuario = :usuario,
            @HHost = :host,
            @semaforo = :semaforo,
            @NNota = :nota
        """
    )
    
    try:
        db.execute(sql, {
            'periodo': periodo,
            'unidad': unidad_sigla,
            'usuario': usuario,
            'host': host,
            'semaforo': int(semaforo),
            'nota': nota or '',
        })
        db.commit()
        print(f"✅ SP_Valida_Matricula ejecutado exitosamente")
    except Exception as e:
        print(f"❌ Error al ejecutar SP_Valida_Matricula: {str(e)}")
        db.rollback()
        raise


def execute_sp_rechaza_matricula(
    db: Session,
    periodo: str,
    unidad_sigla: str,
    usuario: str,
    host: str,
    nota: str
) -> None:
    """
    Ejecuta SP_Rechaza_Matricula.
    Este SP se ejecuta cuando un rol de validación (4 o 5) rechaza la matrícula.
    """
    sql = text(
        """
        EXEC [dbo].[SP_Rechaza_Matricula]
            @PPeriodo = :periodo,
            @UUnidad_Academica = :unidad,
            @UUsuario = :usuario,
            @HHost = :host,
            @NNota = :nota
        """
    )
    
    try:
        db.execute(sql, {
            'periodo': periodo,
            'unidad': unidad_sigla,
            'usuario': usuario,
            'host': host,
            'nota': nota or '',
        })
        db.commit()
        print(f"✅ SP_Rechaza_Matricula ejecutado exitosamente")
    except Exception as e:
        print(f"❌ Error al ejecutar SP_Rechaza_Matricula: {str(e)}")
        db.rollback()
        raise

