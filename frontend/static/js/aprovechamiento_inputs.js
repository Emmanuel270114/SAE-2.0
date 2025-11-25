// Configuración global para los inputs de Aprovechamiento
const APROVECHAMIENTO_CONFIG = {
    inputStyles: {
        container: 'display:inline-flex;flex-direction:row;gap:6px;justify-content:center;align-items:center;width:auto;',
        boxMale: 'display:inline-flex;align-items:center;gap:3px;padding:2px 4px;background:#e3f2fd;border-radius:4px;border:1px solid #90caf9;line-height:1;',
        boxFemale: 'display:inline-flex;align-items:center;gap:3px;padding:2px 4px;background:#fce4ec;border-radius:4px;border:1px solid #f48fb1;line-height:1;',
        labelMale: 'font-weight:700;color:#1976d2;font-size:11px;min-width:14px;text-align:center;',
        labelFemale: 'font-weight:700;color:#c2185b;font-size:11px;min-width:14px;text-align:center;',
        inputMale: 'width:42px;padding:2px 3px;border:2px solid #2196f3;border-radius:3px;background:#fff;color:#1976d2;font-weight:600;text-align:center;font-size:11px;line-height:1.1;',
        inputFemale: 'width:42px;padding:2px 3px;border:2px solid #e91e63;border-radius:3px;background:#fff;color:#c2185b;font-weight:600;text-align:center;font-size:11px;line-height:1.1;',
        inputFilled: 'border-color: #4caf50; background-color: #e8f5e9;'
    },
    labels: {
        male: 'H',
        female: 'M'
    }
};

// Función para crear un input de aprovechamiento (Solo requiere el ID del aprovechamiento y Sexo)
function crearInputAprovechamiento(aprovechamientoId, sexo, valor = '') {
    const isMale = sexo === 'M';
    const label = isMale ? APROVECHAMIENTO_CONFIG.labels.male : APROVECHAMIENTO_CONFIG.labels.female;
    const boxStyle = isMale ? APROVECHAMIENTO_CONFIG.inputStyles.boxMale : APROVECHAMIENTO_CONFIG.inputStyles.boxFemale;
    const labelStyle = isMale ? APROVECHAMIENTO_CONFIG.inputStyles.labelMale : APROVECHAMIENTO_CONFIG.inputStyles.labelFemale;
    const inputStyle = isMale ? APROVECHAMIENTO_CONFIG.inputStyles.inputMale : APROVECHAMIENTO_CONFIG.inputStyles.inputFemale;
    
    // El ID del input ahora es: input_{aprovechamientoId}_{sexo}
    return `<div class="aprovechamiento-box ${isMale ? 'aprovechamiento-hombre' : 'aprovechamiento-mujer'}" style="${boxStyle}">
        <span class="matricula-label" style="${labelStyle}">${label}</span>
        <input type="number" 
               id="input_${aprovechamientoId}_${sexo}" 
               value="${valor}" 
               min="0" 
               class="input-aprovechamiento-nueva" 
               data-aprovechamiento="${aprovechamientoId}" 
               data-sexo="${sexo}" 
               oninput="this.value = this.value.replace(/[^0-9]/g, '')" 
               style="${inputStyle}" placeholder="">
    </div>`;
}

// Función para crear una celda completa con ambos sexos para un concepto de aprovechamiento
function crearCeldaAprovechamiento(aprovechamientoId, valorM = '', valorF = '') {
    const containerStyle = APROVECHAMIENTO_CONFIG.inputStyles.container;
    return `<div class="aprovechamiento-pair-horizontal" style="${containerStyle}">
        ${crearInputAprovechamiento(aprovechamientoId, 'M', valorM)}
        ${crearInputAprovechamiento(aprovechamientoId, 'F', valorF)}
    </div>`;
}