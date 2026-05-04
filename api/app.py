from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from bgp.exceptions import (
    BgpAutomacaoError,
    IrrValidationError,
    RouterConnectionError,
    RouterInventoryError,
    UserCancelledError,
)
from api.routers import sessao, roteadores, relatorios

app = FastAPI(
    title="BGP Huawei Automation API",
    description="API REST para provisionamento de sessões BGP em roteadores Huawei NE8000.",
    version="2.0.0",
)


@app.exception_handler(IrrValidationError)
async def irr_error_handler(request: Request, exc: IrrValidationError) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": str(exc)})


@app.exception_handler(RouterConnectionError)
async def conn_error_handler(request: Request, exc: RouterConnectionError) -> JSONResponse:
    return JSONResponse(status_code=503, content={"detail": str(exc)})


@app.exception_handler(RouterInventoryError)
async def inventory_error_handler(request: Request, exc: RouterInventoryError) -> JSONResponse:
    return JSONResponse(status_code=500, content={"detail": str(exc)})


@app.exception_handler(UserCancelledError)
async def cancelled_error_handler(request: Request, exc: UserCancelledError) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(BgpAutomacaoError)
async def bgp_error_handler(request: Request, exc: BgpAutomacaoError) -> JSONResponse:
    return JSONResponse(status_code=500, content={"detail": str(exc)})


app.include_router(sessao.router, prefix="/sessao", tags=["Sessão BGP"])
app.include_router(roteadores.router, prefix="/roteadores", tags=["Roteadores"])
app.include_router(relatorios.router, prefix="/relatorios", tags=["Relatórios"])
