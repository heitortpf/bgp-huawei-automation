from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

router = APIRouter()

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


@router.get("/{nome}")
async def download_relatorio(nome: str) -> FileResponse:
    if not nome.endswith(".pdf") or "/" in nome or "\\" in nome:
        raise HTTPException(status_code=400, detail="Nome de relatório inválido.")
    path = _PROJECT_ROOT / nome
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Relatório '{nome}' não encontrado.")
    return FileResponse(path=str(path), media_type="application/pdf", filename=nome)
