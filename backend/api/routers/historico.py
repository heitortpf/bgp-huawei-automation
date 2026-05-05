import asyncio
from fastapi import APIRouter, Depends, HTTPException

from bgp.db import listar_sessoes, buscar_sessao
from api.auth import get_current_user
from api.schemas import ExecutionResultResponse, HistoricoItemResponse

router = APIRouter()


def _to_response(row: dict) -> HistoricoItemResponse:
    return HistoricoItemResponse(
        id=row["id"],
        timestamp=row["timestamp"],
        nome_cliente=row["nome_cliente"],
        neighbor_ip=row["neighbor_ip"],
        local_as=row["local_as"],
        neighbor_as=row["neighbor_as"],
        roteadores=row["roteadores"],
        resultados=[
            ExecutionResultResponse(
                host=r["host"],
                status=r["status"],
                duracao_s=r["duracao_s"],
                backup_sha256=r.get("backup_sha256", "-"),
                display_bgp_peer=r.get("display_bgp_peer", ""),
                bgp_display_this=r.get("bgp_display_this", ""),
                recorte_cliente=r.get("recorte_cliente", ""),
            )
            for r in row["resultados"]
        ],
        relatorio_nome=row.get("relatorio_nome"),
    )


@router.get("", response_model=list[HistoricoItemResponse])
async def listar_historico(_: str = Depends(get_current_user)) -> list[HistoricoItemResponse]:
    rows = await asyncio.to_thread(listar_sessoes)
    return [_to_response(r) for r in rows]


@router.get("/{id}", response_model=HistoricoItemResponse)
async def buscar_historico_por_id(id: int, _: str = Depends(get_current_user)) -> HistoricoItemResponse:
    row = await asyncio.to_thread(buscar_sessao, id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Sessão #{id} não encontrada.")
    return _to_response(row)
