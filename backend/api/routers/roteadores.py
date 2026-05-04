from fastapi import APIRouter, Depends, HTTPException

from bgp.models import RouterConfig
from bgp.router_io import ler_routers_txt, acrescentar_router, remover_router
from bgp.exceptions import RouterInventoryError
from api.auth import get_current_user
from api.schemas import RouterIn, RouterOut

router = APIRouter()


@router.get("", response_model=list[RouterOut])
async def listar_roteadores(_: str = Depends(get_current_user)) -> list[RouterOut]:
    try:
        routers = ler_routers_txt()
    except RouterInventoryError:
        return []
    return [RouterOut(host=r.host, username=r.username, port=r.port) for r in routers]


@router.post("", response_model=RouterOut, status_code=201)
async def adicionar_roteador(body: RouterIn, _: str = Depends(get_current_user)) -> RouterOut:
    acrescentar_router(RouterConfig(
        host=body.host,
        username=body.username,
        password=body.password,
        port=body.port,
    ))
    return RouterOut(host=body.host, username=body.username, port=body.port)


@router.delete("/{host}", status_code=204)
async def remover_roteador(host: str, _: str = Depends(get_current_user)) -> None:
    if not remover_router(host):
        raise HTTPException(status_code=404, detail=f"Roteador '{host}' não encontrado.")
