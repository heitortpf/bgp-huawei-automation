import os
import logging
from datetime import datetime
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    Preformatted, PageBreak,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from bgp.config import EMPRESA
from bgp.models import ExecutionResult
from bgp.utils import sha256_file, filesize_bytes

logger = logging.getLogger(__name__)


def _build_pdf(
    path_pdf: str,
    resultados: list[ExecutionResult],
    pdf_sha256: str,
    pdf_size: str,
    routers_txt_path: str,
    routers_txt_sha256: str,
    routers_txt_size: str,
) -> None:
    doc = SimpleDocTemplate(path_pdf, pagesize=A4)
    styles = getSampleStyleSheet()
    code_style = ParagraphStyle(
        name="CodeBlock",
        parent=styles["Normal"],
        fontName="Courier",
        fontSize=8.3,
        leading=10,
        alignment=TA_LEFT,
    )

    elems = []
    elems.append(Paragraph("Relatório Automação BGP Huawei (NE8000)", styles["Title"]))
    elems.append(Paragraph(f"Empresa: {EMPRESA}", styles["Normal"]))
    elems.append(Paragraph(datetime.now().strftime("%d/%m/%Y %H:%M:%S"), styles["Normal"]))
    elems.append(Spacer(1, 12))

    tabela = [["Roteador", "Status", "Duração (s)", "Backup", "Tam (bytes)", "SHA256 (backup)"]]
    for r in resultados:
        tabela.append([
            r.host, r.status, str(r.duracao_s),
            r.backup_path, r.backup_size, r.backup_sha256,
        ])

    t = Table(tabela, repeatRows=1, colWidths=[80, 95, 55, 120, 55, 140])
    t.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 1, colors.black),
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("FONTSIZE", (0, 0), (-1, -1), 7.3),
    ]))
    elems.append(t)
    elems.append(PageBreak())

    elems.append(Paragraph("Auditoria por roteador", styles["Heading2"]))
    elems.append(Spacer(1, 10))

    for idx, r in enumerate(resultados, start=1):
        elems.append(Paragraph(f"{idx}. Roteador: {r.host}", styles["Heading3"]))
        elems.append(Paragraph(f"Status: {r.status} | Duração: {r.duracao_s}s", styles["Normal"]))
        elems.append(Paragraph(f"Backup: {r.backup_path} | Tam (bytes): {r.backup_size}", styles["Normal"]))
        elems.append(Paragraph(f"SHA256 (backup): {r.backup_sha256}", styles["Normal"]))
        elems.append(Spacer(1, 10))

        elems.append(Paragraph("1) display bgp peer", styles["Heading4"]))
        elems.append(Preformatted(r.display_bgp_peer, code_style))
        elems.append(Spacer(1, 12))

        elems.append(Paragraph("2) BGP (display this)", styles["Heading4"]))
        elems.append(Preformatted(r.bgp_display_this, code_style))
        elems.append(Spacer(1, 12))

        elems.append(Paragraph("3) Recorte do current-configuration (cliente/policies/prefix-lists/peer)", styles["Heading4"]))
        elems.append(Preformatted(r.recorte_cliente, code_style))
        elems.append(Spacer(1, 16))
        elems.append(PageBreak())

    elems.append(Paragraph("Integridade do Relatório", styles["Heading2"]))
    elems.append(Spacer(1, 12))
    elems.append(Paragraph("SHA256 do próprio PDF (auditoria):", styles["Normal"]))
    elems.append(Preformatted(pdf_sha256, code_style))
    elems.append(Paragraph(f"Tamanho do PDF (bytes): {pdf_size}", styles["Normal"]))
    elems.append(Spacer(1, 12))
    elems.append(Paragraph("Inventário utilizado (routers.txt):", styles["Normal"]))
    elems.append(Paragraph(f"Caminho: {routers_txt_path}", styles["Normal"]))
    elems.append(Paragraph(f"Tamanho (bytes): {routers_txt_size}", styles["Normal"]))
    elems.append(Paragraph("SHA256 (routers.txt):", styles["Normal"]))
    elems.append(Preformatted(routers_txt_sha256, code_style))

    doc.build(elems)


def gerar_relatorio(resultados: list[ExecutionResult], routers_txt_path: str) -> tuple[str, str, str]:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    pdf_tmp = f"relatorio_huawei_{ts}_tmp.pdf"
    pdf_final = f"relatorio_huawei_{ts}.pdf"

    routers_sha = sha256_file(routers_txt_path)
    routers_size = filesize_bytes(routers_txt_path)

    _build_pdf(pdf_tmp, resultados, "(calculando...)", "-", routers_txt_path, routers_sha, routers_size)
    pdf_hash = sha256_file(pdf_tmp)
    pdf_size = filesize_bytes(pdf_tmp)
    _build_pdf(pdf_final, resultados, pdf_hash, pdf_size, routers_txt_path, routers_sha, routers_size)

    try:
        os.remove(pdf_tmp)
    except Exception:
        pass

    logger.info(f"Relatório gerado: {pdf_final}")
    logger.info(f"SHA256 do PDF: {pdf_hash}")
    logger.info(f"routers.txt: {routers_txt_path} | SHA256: {routers_sha}")
    return pdf_final, pdf_hash, routers_sha
