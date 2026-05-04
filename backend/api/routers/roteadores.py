from fastapi import APIRouter, Depends, HTTPException

from bgp.router_io import ler_routers_txt
from bgp.config import ARQUIVO_ROUTERS
from api.auth import get_current_user
from api.schemas import RouterIn, RouterOut

router = APIRouter()


@router.get("", response_model=list[RouterOut])
async def listar_roteadores(_: str = Depends(get_current_user)) -> list[RouterOut]:
    routers = ler_routers_txt()
    return [RouterOut(host=r.host, username=r.username, port=r.port) for r in routers]


@router.post("", response_model=RouterOut, status_code=201)
async def adicionar_roteador(body: RouterIn, _: str = Depends(get_current_user)) -> RouterOut:
    with open(ARQUIVO_ROUTERS, "a", encoding="utf-8") as f:
        f.write(f"{body.host},{body.username},{body.password},{body.port}\n")
    return RouterOut(host=body.host, username=body.username, port=body.port)


@router.delete("/{host}", status_code=204)
async def remover_roteador(host: str, _: str = Depends(get_current_user)) -> None:
    routers = ler_routers_txt()
    restantes = [r for r in routers if r.host != host]
    if len(restantes) == len(routers):
        raise HTTPException(status_code=404, detail=f"Roteador '{host}' não encontrado.")
    with open(ARQUIVO_ROUTERS, "w", encoding="utf-8") as f:
        for r in restantes:
            f.write(f"{r.host},{r.username},{r.password},{r.port}\n")
