from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from bgp.exceptions import (
    BgpAutomacaoError,
    IrrValidationError,
    RouterConnectionError,
    RouterInventoryError,
    UserCancelledError,
)
from api.routers import auth, sessao, roteadores, relatorios

app = FastAPI(
    title="BGP Huawei Automation API",
    description="API REST para provisionamento de sessões BGP em roteadores Huawei NE8000.",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:4173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(IrrValidationError)
async def irr_error_handler(_request: Request, exc: IrrValidationError) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": str(exc)})


@app.exception_handler(RouterConnectionError)
async def conn_error_handler(_request: Request, exc: RouterConnectionError) -> JSONResponse:
    return JSONResponse(status_code=503, content={"detail": str(exc)})


@app.exception_handler(RouterInventoryError)
async def inventory_error_handler(_request: Request, exc: RouterInventoryError) -> JSONResponse:
    return JSONResponse(status_code=500, content={"detail": str(exc)})


@app.exception_handler(UserCancelledError)
async def cancelled_error_handler(_request: Request, exc: UserCancelledError) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(BgpAutomacaoError)
async def bgp_error_handler(_request: Request, exc: BgpAutomacaoError) -> JSONResponse:
    return JSONResponse(status_code=500, content={"detail": str(exc)})


app.include_router(auth.router, prefix="/api/auth", tags=["Auth"])
app.include_router(sessao.router, prefix="/api/sessao", tags=["Sessão BGP"])
app.include_router(roteadores.router, prefix="/api/roteadores", tags=["Roteadores"])
app.include_router(relatorios.router, prefix="/api/relatorios", tags=["Relatórios"])
