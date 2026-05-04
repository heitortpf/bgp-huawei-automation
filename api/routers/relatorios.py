from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from api.auth import get_current_user

router = APIRouter()

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


@router.get("", response_model=list[str])
async def listar_relatorios(_: str = Depends(get_current_user)) -> list[str]:
    return sorted(p.name for p in _PROJECT_ROOT.glob("relatorio_huawei_*.pdf"))


@router.get("/{nome}")
async def download_relatorio(nome: str, _: str = Depends(get_current_user)) -> FileResponse:
    if not nome.endswith(".pdf") or "/" in nome or "\\" in nome:
        raise HTTPException(status_code=400, detail="Nome de relatório inválido.")
    path = _PROJECT_ROOT / nome
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Relatório '{nome}' não encontrado.")
    return FileResponse(path=str(path), media_type="application/pdf", filename=nome)
