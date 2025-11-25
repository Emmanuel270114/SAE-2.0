#backend.main.py
from backend.api import registro
from backend.api import login
from backend.api import usuarios
from backend.api import mod_principal
from backend.api import unidad_academica
from backend.api import matricula_sp
from backend.api import aprovechamiento_sp
from backend.api import recuperacion
from backend.api.catalogos import domicilios, estatus, periodos, programas, roles, semaforo, modulos, objetos
from backend.core.templates import static
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, RedirectResponse

app = FastAPI()
app.mount("/static", static, name="static")
app.include_router(registro.router, prefix="/registro")
app.include_router(login.router , prefix="/login")
app.include_router(usuarios.router , prefix="/usuarios")
app.include_router(mod_principal.router , prefix="/mod_principal")
app.include_router(unidad_academica.router , prefix="/unidad_academica")
app.include_router(matricula_sp.router , prefix="/matricula")
app.include_router(aprovechamiento_sp.router , prefix="/aprovechamiento")
app.include_router(domicilios.router)
app.include_router(periodos.router)
app.include_router(programas.router)
app.include_router(semaforo.router)
app.include_router(estatus.router)
app.include_router(modulos.router)
app.include_router(objetos.router)

app.include_router(roles.router)


app.include_router(recuperacion.router)

@app.get("/", response_class=HTMLResponse)
async def root():
    return RedirectResponse(url="/login")