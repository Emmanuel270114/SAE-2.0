
"""Este archivo contiene las funciones CRUD para el modelo Matricula y consultas específicas usando SP."""

from backend.database.models.Matricula import Matricula
from backend.database.models.CatPeriodo import CatPeriodo as Periodo
from backend.database.models.CatUnidadAcademica import CatUnidadAcademica as Unidad_Academica
from backend.database.models.CatNivel import CatNivel as Nivel

from sqlalchemy import select, text
from sqlalchemy.orm import Session
from typing import Dict, List, Any, Optional, Tuple


############################__________________FUNCIONES CREATE____________________________############################
def create_matricula(db: Session, matricula_data: Dict[str, Any]) -> Matricula:
    """Crear una nueva entrada de matrícula."""
    new_matricula = Matricula(**matricula_data)
    db.add(new_matricula)
    db.commit()
    db.refresh(new_matricula)
    return new_matricula


############################__________________FUNCIONES READ____________________________############################
def get_matricula_by_filters(
    db: Session,
    id_unidad_academica: Optional[int] = None,
    id_programa: Optional[int] = None,
    id_modalidad: Optional[int] = None,
    id_semestre: Optional[int] = None,
    id_turno: Optional[int] = None,
    id_nivel: Optional[int] = None,
) -> List[Matricula]:
    """Obtener registros de matricula aplicando filtros opcionales."""
    query = db.query(Matricula)
    
    if id_unidad_academica is not None:
        query = query.filter(Matricula.Id_Unidad_Academica == id_unidad_academica)
    if id_programa is not None:
        query = query.filter(Matricula.Id_Programa == id_programa)
    if id_modalidad is not None:
        query = query.filter(Matricula.Id_Modalidad == id_modalidad)
    if id_semestre is not None:
        query = query.filter(Matricula.Id_Semestre == id_semestre)
    if id_turno is not None:
        query = query.filter(Matricula.Id_Turno == id_turno)
    if id_nivel is not None:
        query = query.filter(Matricula.Id_Nivel == id_nivel)
        
    return query.all()


def get_distinct_programa_ids_by_unidad(db: Session, id_unidad_academica: int) -> List[int]:
    """Obtener IDs únicos de programas para una unidad académica específica."""
    result = db.query(Matricula.Id_Programa).filter(
        Matricula.Id_Unidad_Academica == id_unidad_academica
    ).distinct().all()
    return [p.Id_Programa for p in result]


def get_distinct_grupo_edad_ids_by_unidad_nivel(db: Session, id_unidad_academica: int, id_nivel: int) -> List[int]:
    """Obtener IDs únicos de grupos de edad para una unidad académica y nivel específicos."""
    result = db.query(Matricula.Id_Grupo_Edad).filter(
        Matricula.Id_Nivel == id_nivel,
        Matricula.Id_Unidad_Academica == id_unidad_academica
    ).distinct().all()
    return [g.Id_Grupo_Edad for g in result]


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


def execute_sp_consulta_matricula(
    db: Session,
    unidad_sigla: str,
    periodo: str,
    nivel: str,
    usuario: str = 'sistema',
    host: str = 'localhost'
) -> Tuple[List[Dict[str, Any]], List[str], Optional[str]]:
    """
    Ejecutar el SP SP_Consulta_Matricula_Unidad_Academica y devolver las filas normalizadas.
    
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
        # Usar conexión raw para manejar múltiples result sets
        connection = db.connection()
        
        # Ejecutar el SP con parámetros seguros (incluyendo @UUsuario y @HHost)
        sql = text("""
            EXEC SP_Consulta_Matricula_Unidad_Academica 
                @UUnidad_Academica = :unidad, 
                @PPeriodo = :periodo, 
                @NNivel = :nivel, 
                @UUsuario = :usuario, 
                @HHost = :host
        """)
        
        result = connection.execute(sql, {
            'unidad': unidad_sigla, 
            'periodo': periodo, 
            'nivel': nivel,
            'usuario': usuario,
            'host': host
        })
        
        # PRIMER RESULT SET: Datos de matrícula
        rows = result.fetchall()

        # Obtener nombres de columnas si el driver los provee
        try:
            columns = list(result.keys())
        except Exception:
            columns = []

        # Normalizar filas a listas de dicts serializables
        rows_list = []
        for row in rows:
            try:
                row_dict = safe_row_to_dict(row, columns)

                # Convertir tipos no serializables a string cuando sea necesario
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
        
        # SEGUNDO RESULT SET: Nota de rechazo (si existe)
        nota_rechazo = None
        try:
            # Usar nextset() en el cursor subyacente
            if hasattr(result, 'cursor') and hasattr(result.cursor, 'nextset'):
                if result.cursor.nextset():
                    nota_rows = result.cursor.fetchall()
                    if nota_rows and len(nota_rows) > 0:
                        # El SP devuelve una sola columna 'Nota'
                        nota_rechazo = nota_rows[0][0] if nota_rows[0][0] else None
                        if nota_rechazo:
                            print(f"📋 Nota de rechazo capturada del SP: {nota_rechazo[:100]}...")
        except Exception as e:
            print(f"⚠️ No se pudo capturar segundo result set (Nota): {e}")

        return rows_list, columns, nota_rechazo

    except Exception as e:
        print(f"Error ejecutando SP: {e}")
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
    print(f"Aviso: Periodo '{periodo_input}' no encontrado, usando default: {default}")
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
