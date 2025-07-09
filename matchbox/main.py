# matchbox/main.py 1
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
#from matchbox.main import app
from matchbox.modes.classic_solo import router as classic_solo_router
from matchbox.modes.classic_pvp import router as classic_pvp_router

app = FastAPI()
app.include_router(classic_solo_router, prefix="/classic/solo")
app.include_router(classic_pvp_router)#, prefix="/classic/pvp"
app.mount("/", StaticFiles(directory="public", html=True), name="static")
