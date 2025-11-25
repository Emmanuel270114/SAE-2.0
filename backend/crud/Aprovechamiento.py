from backend.database.models.Aprovechamiento import Aprovechamiento
from backend.database.models.CatPeriodo import CatPeriodo as Periodo
from backend.database.models.CatUnidadAcademica import CatUnidadAcademica as Unidad_Academica
from backend.database.models.CatNivel import CatNivel as Nivel

from sqlalchemy import select, text
from sqlalchemy.orm import Session
from typing import Dict, List, Any, Optional, Tuple
import logging

logger = logging.getLogger(__name__)

def create_aprovehcamiento(db: Session, aprovechamiento_data: Dict[str, Any]) -> Aprovechamiento:
    """Crear una nueva entrada de aprovechamiento."""
    new_aprovechamiento = Aprovechamiento(**aprovechamiento_data)
    db.add(new_aprovechamiento)
    db.commit()
    db.refresh(new_aprovechamiento)
    return new_aprovechamiento

def get_aprovechamiento_by_filters(
    db: Session,
    id_unidad_academica: Optional[int] = None,
    id_programa: Optional[int] = None,
    id_modalidad: Optional[int] = None,
    id_semestre: Optional[int] = None,
    id_turno: Optional[int] = None,
    id_nivel: Optional[int] = None,
) -> List[Aprovechamiento]:
    """Obtener registros de aprovechamiento aplicando filtros opcionales."""
    query = db.query(Aprovechamiento)
    
    if id_unidad_academica is not None:
        query = query.filter(Aprovechamiento.Id_Unidad_Academica == id_unidad_academica)
    if id_programa is not None:
        query = query.filter(Aprovechamiento.Id_Programa == id_programa)
    if id_modalidad is not None:
        query = query.filter(Aprovechamiento.Id_Modalidad == id_modalidad)
    if id_semestre is not None:
        query = query.filter(Aprovechamiento.Id_Semestre == id_semestre)
    if id_turno is not None:
        query = query.filter(Aprovechamiento.Id_Turno == id_turno)
    if id_nivel is not None:
        query = query.filter(Aprovechamiento.Id_Nivel == id_nivel)
        
    return query.all()

def get_distinct_programa_ids_by_unidad(db: Session, id_unidad_academica: int) -> List[int]:
    """Obtener IDs únicos de programas para una unidad académica específica."""
    result = db.query(Aprovechamiento.Id_Programa).filter(
        Aprovechamiento.Id_Unidad_Academica == id_unidad_academica
    ).distinct().all()
    return [p.Id_Programa for p in result]

############################__________________STORED PROCEDURES____________________________############################
def safe_row_to_dict(row, cols=None) -> Dict[str, Any]:
    """Convertir fila de resultado de SP a diccionario de forma segura."""
    # Priorizar mapping API si existe
    try:
        if hasattr(row, '_mapping'):
            return dict(row._mapping)
    except Exception:
        pass
    try:
        if hasattr(row, '_asdict'):
            return row._asdict()
    except Exception:
        pass
    # Si es tupla/lista, usar cols para mapear
    try:
        if isinstance(row, (list, tuple)) and cols:
            return {cols[i]: row[i] for i in range(min(len(cols), len(row)))}
    except Exception:
        pass
    # Fallback: intentar dict(row)
    try:
        return dict(row)
    except Exception:
        # última opción: inspeccionar atributos públicos
        rd = {}
        for attr in dir(row):
            if not attr.startswith('_') and not callable(getattr(row, attr)):
                try:
                    rd[attr] = getattr(row, attr)
                except Exception:
                    continue
        return rd


def execute_sp_consulta_aprovechamiento(
    db: Session,
    unidad_sigla: str,
    periodo: str,
    nivel: str,
    usuario: str = 'sistema',
    host: str = 'localhost'
) -> Tuple[List[Dict[str, Any]], List[str], Optional[str]]:
    """
    Ejecutar el SP SP_Consulta_Aprovechamiento_Unidad_Academica y devolver las filas normalizadas.
    
    Args:
        db: Sesión de base de datos
        unidad_sigla: Sigla de la unidad académica (ej: 'ESE', 'ESCOM')
        periodo: Periodo académico (ej: '2025-2026/1')
        nivel: Nivel educativo (ej: 'Posgrado', 'Licenciatura')
        usuario: Nombre del usuario que ejecuta la consulta
        host: Host desde donde se realiza la petición
    
    Returns:
        Tuple[List[Dict], List[str], Optional[str]]: (filas como dicts, nombres de columnas, nota de rechazo)
    """
    try:
        # Ejecutar el SP con parámetros seguros (incluyendo @UUsuario y @HHost)
        sql = text("""
            EXEC SP_Consulta_Aprovechamiento_Unidad_Academica 
                @UUnidad_Academica = :unidad, 
                @PPeriodo = :periodo, 
                @NNivel = :nivel, 
                @UUsuario = :usuario, 
                @HHost = :host
        """)
        result = db.execute(sql, {
            'unidad': unidad_sigla, 
            'periodo': periodo, 
            'nivel': nivel,
            'usuario': usuario,
            'host': host
        })

        rows_list = []
        columns = []
        nota_rechazo = None

        # Preferir el cursor bruto cuando el driver lo expone (soporta nextset)
        raw_cursor = getattr(result, 'cursor', None)
        if raw_cursor is not None and hasattr(raw_cursor, 'nextset'):
            try:
                set_index = 0
                # Iterar todos los result sets: algunos drivers requieren avanzar hasta encontrar uno con description
                while True:
                    desc = getattr(raw_cursor, 'description', None)
                    if desc:
                        cols = [d[0] for d in desc]
                        try:
                            rows_raw = raw_cursor.fetchall()
                        except Exception as e:
                            logger.warning("No se pudo fetchall en result set %d: %s", set_index, e)
                            rows_raw = []

                        if rows_raw:
                            # Si es el primer result set que tiene varias columnas, lo tratamos como datos principales
                            if set_index == 0 and len(cols) > 1:
                                columns = cols
                                for row in rows_raw:
                                    try:
                                        row_dict = safe_row_to_dict(row, columns)
                                        for k, v in list(row_dict.items()):
                                            if isinstance(v, (bytes, bytearray)):
                                                try:
                                                    row_dict[k] = v.decode('utf-8', errors='ignore')
                                                except Exception:
                                                    row_dict[k] = str(v)
                                            elif not isinstance(v, (str, int, float, bool, type(None))):
                                                row_dict[k] = str(v)
                                        rows_list.append(row_dict)
                                    except Exception:
                                        continue
                            else:
                                # Podría ser la nota (un solo campo) u otros result sets
                                if len(cols) == 1 and rows_raw and rows_raw[0][0]:
                                    nota_rechazo = rows_raw[0][0]
                                    logger.info("Nota de rechazo capturada del SP: %s...", str(nota_rechazo)[:100])
                                else:
                                    logger.debug("Result set %d recibido con columnas %s (no procesado)", set_index, cols)
                    else:
                        logger.debug("Result set %d sin description (no es consulta), se salta", set_index)

                    set_index += 1
                    try:
                        has_next = raw_cursor.nextset()
                    except Exception as e:
                        logger.debug("raw_cursor.nextset() lanzó excepción en set %d: %s", set_index - 1, e)
                        break
                    if not has_next:
                        break
            except Exception as e:
                logger.exception("Error iterando result sets del cursor bruto: %s", e)
        else:
            # Fallback: usar el objeto result de SQLAlchemy
            try:
                rows = result.fetchall()
            except Exception:
                rows = []

            try:
                columns = list(result.keys())
            except Exception:
                columns = []

            for row in rows:
                try:
                    row_dict = safe_row_to_dict(row, columns)
                    for k, v in list(row_dict.items()):
                        if isinstance(v, (bytes, bytearray)):
                            try:
                                row_dict[k] = v.decode('utf-8', errors='ignore')
                            except Exception:
                                row_dict[k] = str(v)
                        elif not isinstance(v, (str, int, float, bool, type(None))):
                            row_dict[k] = str(v)
                    rows_list.append(row_dict)
                except Exception:
                    continue

            # Intentar capturar segundo result set si el result expone nextset
            try:
                if hasattr(result, 'nextset') and result.nextset():
                    nota_rows = result.fetchall()
                    if nota_rows and len(nota_rows) > 0 and nota_rows[0][0]:
                        nota_rechazo = nota_rows[0][0]
                        logger.info("Nota de rechazo capturada del SP: %s...", str(nota_rechazo)[:100])
            except Exception as e:
                logger.warning("No se pudo capturar segundo result set (Nota): %s", e)

        return rows_list, columns, nota_rechazo

    except Exception as e:
        logger.exception("Error ejecutando SP: %s", e)
        return [], [], None


def resolve_periodo_by_id_or_literal(db: Session, periodo_input: str, default: str = "2025-2026/1") -> str:
    """
    Resolver periodo por ID numérico o por literal. Si no se encuentra, usar default.
    
    Args:
        db: Sesión de base de datos
        periodo_input: ID como string ('9') o literal ('2025-2026/1')
        default: Periodo por defecto si no se encuentra
        
    Returns:
        str: Periodo literal para usar en el SP
    """
    if not periodo_input:
        return default
        
    try:
        # Intentar interpretar como ID numérico
        periodo_id = int(periodo_input)
        periodo_obj = db.query(Periodo).filter(Periodo.Id_Periodo == periodo_id).first()
        if periodo_obj:
            return periodo_obj.Periodo
    except (ValueError, TypeError):
        # No es numérico, buscar por literal
        periodo_obj = db.query(Periodo).filter(Periodo.Periodo == periodo_input).first()
        if periodo_obj:
            return periodo_obj.Periodo
    
    # Si no se encuentra, usar default
    logger.warning("Periodo '%s' no encontrado, usando default: %s", periodo_input, default)
    return default


def get_unidad_and_nivel_info(db: Session, id_unidad: int, id_nivel: int) -> Tuple[Optional[str], Optional[str]]:
    """
    Obtener sigla de unidad académica y nombre de nivel por sus IDs.
    
    Returns:
        Tuple[Optional[str], Optional[str]]: (sigla_unidad, nombre_nivel)
    """
    unidad = db.query(Unidad_Academica).filter(Unidad_Academica.Id_Unidad_Academica == id_unidad).first()
    nivel = db.query(Nivel).filter(Nivel.Id_Nivel == id_nivel).first()
    
    unidad_sigla = unidad.Sigla if unidad else None
    nivel_nombre = nivel.Nivel if nivel else None
    
    return unidad_sigla, nivel_nombre

