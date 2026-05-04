import asyncio
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException

from bgp.models import BgpSessionConfig
from bgp.commands import build_huawei_commands
from bgp.irr import buscar_prefixos_por_asn, validar_asn_prefixo
from bgp.router_io import ler_routers_txt
from bgp.connector import executar_bgp
from bgp.report import gerar_relatorio
from bgp.config import ARQUIVO_ROUTERS
from bgp.exceptions import IrrValidationError
from api.auth import get_current_user

from api.schemas import (
    PreviewRequest,
    PreviewResponse,
    ValidarIrrRequest,
    ValidarIrrResponse,
    AplicarRequest,
    AplicarResponse,
    ExecutionResultResponse,
    PrefixosResponse,
)

router = APIRouter()


def _to_session_config(req) -> BgpSessionConfig:
    s = req.sessao
    return BgpSessionConfig(
        local_as=s.local_as,
        neighbor_ip=s.neighbor_ip,
        neighbor_as=s.neighbor_as,
        nome_cliente=s.nome_cliente,
        prefixes_ipv4=s.prefixes_ipv4,
        prefixes_ipv6=s.prefixes_ipv6,
    )


@router.get("/asn/{asn}/prefixos", response_model=PrefixosResponse, tags=["Prefixos"])
async def get_prefixos_por_asn(asn: int, _: str = Depends(get_current_user)) -> PrefixosResponse:
    ipv4, ipv6 = await asyncio.to_thread(buscar_prefixos_por_asn, asn)
    return PrefixosResponse(ipv4=ipv4, ipv6=ipv6)


@router.post("/preview", response_model=PreviewResponse)
async def preview_sessao(body: PreviewRequest, _: str = Depends(get_current_user)) -> PreviewResponse:
    session = _to_session_config(body)
    cmds = build_huawei_commands(session)
    return PreviewResponse(comandos=cmds)


@router.post("/validar-irr", response_model=ValidarIrrResponse)
async def validar_irr(body: ValidarIrrRequest, _: str = Depends(get_current_user)) -> ValidarIrrResponse:
    try:
        await asyncio.to_thread(validar_asn_prefixo, body.prefixos, body.asn_peer)
    except IrrValidationError:
        raise
    return ValidarIrrResponse(ok=True)


@router.post("/aplicar", response_model=AplicarResponse)
async def aplicar_sessao(body: AplicarRequest, _: str = Depends(get_current_user)) -> AplicarResponse:
    session = _to_session_config(body)
    cmds = build_huawei_commands(session)

    todos_routers = ler_routers_txt()

    if body.roteadores is None:
        routers_selecionados = todos_routers
    elif len(body.roteadores) == 0:
        raise HTTPException(status_code=400, detail="Selecione ao menos um roteador.")
    else:
        hosts_solicitados = set(body.roteadores)
        routers_selecionados = [r for r in todos_routers if r.host in hosts_solicitados]
        hosts_nao_encontrados = hosts_solicitados - {r.host for r in routers_selecionados}
        if hosts_nao_encontrados:
            raise HTTPException(
                status_code=404,
                detail=f"Roteadores não encontrados no inventário: {sorted(hosts_nao_encontrados)}",
            )

    resultados = await asyncio.to_thread(
        executar_bgp,
        routers_selecionados,
        session,
        cmds,
        lambda _host, _existing: body.aplicar_se_existir,
    )

    relatorio_nome = None
    relatorio_sha256 = None
    if body.gerar_relatorio:
        pdf_path, pdf_hash, _ = await asyncio.to_thread(
            gerar_relatorio, resultados, ARQUIVO_ROUTERS
        )
        relatorio_nome = Path(pdf_path).name
        relatorio_sha256 = pdf_hash

    return AplicarResponse(
        resultados=[
            ExecutionResultResponse(
                host=r.host,
                status=r.status,
                duracao_s=r.duracao_s,
                backup_sha256=r.backup_sha256,
                display_bgp_peer=r.display_bgp_peer,
                bgp_display_this=r.bgp_display_this,
                recorte_cliente=r.recorte_cliente,
            )
            for r in resultados
        ],
        relatorio_nome=relatorio_nome,
        relatorio_sha256=relatorio_sha256,
    )
