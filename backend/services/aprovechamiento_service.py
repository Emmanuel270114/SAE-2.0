
"""Servicio para operaciones de aprovechamiento usando EXCLUSIVAMENTE Stored Procedures."""

from backend.crud.Aprovechamiento import (
    execute_sp_consulta_aprovechamiento,
    resolve_periodo_by_id_or_literal,
    get_unidad_and_nivel_info,
)

from sqlalchemy.orm import Session
from typing import Dict, List, Any, Optional, Tuple
from sqlalchemy import text
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


def extract_unique_values_from_sp(rows_list: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Extraer valores únicos del SP.
    Para Aprovechamiento, extraemos la columna 'Aprovechamiento' (o el nombre que devuelva el SP).
    """
    aprovechamientos_set = set()
    programas_set = set()
    modalidades_set = set()
    semestres_set = set()
    turnos_set = set()
    
    for row in rows_list:
        # Extraer Aprovechamiento (Concepto)
        # Asumimos que el SP devuelve una columna llamada 'Aprovechamiento'
        if 'Aprovechamiento' in row and row['Aprovechamiento']:
            aprovechamientos_set.add(str(row['Aprovechamiento']))
        
        # Contexto común
        if 'Nombre_Programa' in row and row['Nombre_Programa']:
            programas_set.add(str(row['Nombre_Programa']))
        
        if 'Modalidad' in row and row['Modalidad']:
            modalidades_set.add(str(row['Modalidad']))
        
        if 'Semestre' in row and row['Semestre']:
            semestres_set.add(str(row['Semestre']))
        
        if 'Turno' in row and row['Turno']:
            turnos_set.add(str(row['Turno']))
    
    return {
        'aprovechamientos': sorted(list(aprovechamientos_set)),  # Lista de conceptos
        'programas': sorted(list(programas_set)),
        'modalidades': sorted(list(modalidades_set)),
        'semestres': sorted(list(semestres_set)),
        'turnos': sorted(list(turnos_set))
    }

def get_aprovechamiento_metadata_from_sp(
    db: Session,
    id_unidad_academica: int,
    id_nivel: int,
    periodo_input: Optional[str] = None,
    default_periodo: str = "2025-2026/1",
    usuario: str = 'sistema',
    host: str = 'localhost'
) -> Dict[str, Any]:
    try:
        unidad_sigla, nivel_nombre = get_unidad_and_nivel_info(db, id_unidad_academica, id_nivel)
        logger.debug("Resolved unidad_sigla=%s nivel_nombre=%s for ids %s/%s", unidad_sigla, nivel_nombre, id_unidad_academica, id_nivel)
        
        if not unidad_sigla or not nivel_nombre:
            return {'error': 'No se pudo resolver unidad o nivel', 'aprovechamientos': []}
        
        periodo_nombre = resolve_periodo_by_id_or_literal(db, periodo_input or default_periodo, default_periodo)
        
        rows_list, columns, nota_rechazo = execute_sp_consulta_aprovechamiento(
            db, unidad_sigla, periodo_nombre, nivel_nombre, usuario, host
        )
        logger.debug("SP returned %d rows; columns=%s; nota=%s", len(rows_list), columns, nota_rechazo)
        
        if not rows_list:
            return {'error': 'El SP no devolvió datos', 'aprovechamientos': []}
        
        metadata = extract_unique_values_from_sp(rows_list)
        return metadata
        
    except Exception as e:
        logger.exception("Error getting metadata from SP: %s", e)
        return {'error': str(e), 'aprovechamientos': []}

def execute_aprovechamiento_sp_with_context(
    db: Session,
    id_unidad_academica: int,
    id_nivel: int,
    periodo_input: Optional[str] = None,
    default_periodo: str = "2025-2026/1",
    usuario: str = 'sistema',
    host: str = 'localhost'
) -> Tuple[List[Dict[str, Any]], Dict[str, Any], str, Optional[str]]:
    try:
        unidad_sigla, nivel_nombre = get_unidad_and_nivel_info(db, id_unidad_academica, id_nivel)
        logger.debug("Resolved unidad_sigla=%s nivel_nombre=%s for ids %s/%s", unidad_sigla, nivel_nombre, id_unidad_academica, id_nivel)

        if not unidad_sigla or not nivel_nombre:
            logger.warning("Unidad o nivel no encontrados: unidad=%s nivel=%s", unidad_sigla, nivel_nombre)
            return [], {}, f"Error: Unidad {id_unidad_academica} o Nivel {id_nivel} no encontrados", None

        periodo_nombre = resolve_periodo_by_id_or_literal(db, periodo_input or default_periodo, default_periodo)
        logger.debug("Periodo resuelto para ejecución SP: %s", periodo_nombre)
        
        rows_list, columns, nota_rechazo = execute_sp_consulta_aprovechamiento(
            db, unidad_sigla, periodo_nombre, nivel_nombre, usuario, host
        )
        logger.debug("SP returned %d rows; columns=%s; nota=%s", len(rows_list), columns, nota_rechazo)
        
        # Procesar NULLs
        rows_processed = []
        for row in rows_list:
            processed_row = {}
            for key, value in row.items():
                if value is None or (isinstance(value, str) and value.upper() == 'NULL'):
                    processed_row[key] = ""
                else:
                    processed_row[key] = value
            rows_processed.append(processed_row)
        
        metadata = extract_unique_values_from_sp(rows_processed)
        debug_msg = f"SP ejecutado: {len(rows_processed)} filas."
        logger.info(debug_msg)
        logger.debug("Metadata extraida: %s", metadata)

        return rows_processed, metadata, debug_msg, nota_rechazo
        
    except Exception as e:
        logger.exception("Error SP Aprovechamiento: %s", e)
        return [], {}, str(e), None

# ... (El resto de funciones SP helpers como execute_sp_actualiza... se mantienen igual, solo asegúrate que apunten a los SPs correctos de Aprovechamiento)


# =============================
# SP helpers (centralizar SQL)
# =============================

def execute_sp_actualiza_aprovechamiento_por_unidad_academica(
    db: Session,
    unidad_sigla: str,
    salones: int,
    usuario: str,
    periodo: str,
    host: str,
    nivel: str,
) -> None:
    """Ejecuta SP_Actualiza_Aprovechamiento_Por_Unidad_Academica. Centraliza SQL crudo aquí."""
    sql = text(
        """
        EXEC [dbo].[SP_Actualiza_Aprovechamiento_Por_Unidad_Academica]
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


def execute_sp_actualiza_aprovechamiento_por_semestre_au(
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
    """Ejecuta SP_Actualiza_Aprovechamiento_Por_Semestre_AU y devuelve el último result set como lista de dicts."""
    sql = text(
        """
        EXEC [dbo].[SP_Aprovechamiento_Matricula_Por_Semestre_AU]
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
    # Llamar al helper dejando el parametro `default_periodo` por defecto
    rows, _meta, _dbg, _nota = execute_aprovechamiento_sp_with_context(
        db,
        id_unidad_academica,
        id_nivel,
        periodo_input,
        usuario=usuario,
        host=host,
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


def execute_sp_finaliza_captura_aprovechamiento(
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
    Ejecuta SP_Finaliza_Captura_Aprovechamiento.
    Este SP se ejecuta automáticamente después de SP_Actualiza_Aprovechamiento_Por_Semestre_AU
    para finalizar completamente la captura del semestre.
    """
    sql = text(
        """
        EXEC [dbo].[SP_Finaliza_Captura_Aprovechamiento]
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
        logger.info("SP_Finaliza_Captura_Aprovechamiento ejecutado exitosamente para unidad=%s programa=%s semestre=%s", unidad_sigla, programa_nombre, semestre_nombre)
    except Exception as e:
        logger.exception("Error al ejecutar SP_Finaliza_Captura_Aprovechamiento: %s", e)
        db.rollback()
        raise


def execute_sp_valida_aprovechamiento(
    db: Session,
    periodo: str,
    unidad_sigla: str,
    usuario: str,
    host: str,
    semaforo: int,
    nota: str = ""
) -> None:
    """
    Ejecuta SP_Valida_Aprovechamiento.
    Este SP se ejecuta cuando un rol de validación (4 o 5) aprueba la matrícula.
    """
    sql = text(
        """
        EXEC [dbo].[SP_Valida_Aprovechamiento]
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
        logger.info("SP_Valida_Aprovechamiento ejecutado exitosamente periodo=%s unidad=%s semaforo=%s", periodo, unidad_sigla, semaforo)
    except Exception as e:
        logger.exception("Error al ejecutar SP_Valida_Aprovechamiento: %s", e)
        db.rollback()
        raise


def execute_sp_rechaza_aprovechamiento(
    db: Session,
    periodo: str,
    unidad_sigla: str,
    usuario: str,
    host: str,
    nota: str
) -> None:
    """
    Ejecuta SP_Rechaza_Aprovechamiento.
    Este SP se ejecuta cuando un rol de validación (4 o 5) rechaza la matrícula.
    """
    sql = text(
        """
        EXEC [dbo].[SP_Rechaza_Aprovechamiento]
            @PPeriodo = :periodo,
            @UUnidad_Academica = :unidad,
            @UUsuario = :usuario,
            @HHost = :host,
            @NNota = :nota
        """
    )
    