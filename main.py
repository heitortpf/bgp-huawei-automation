import sys
import logging
from pathlib import Path
from bgp.config import ARQUIVO_ROUTERS, BACKUP_DIR
from bgp.exceptions import BgpAutomacaoError, IrrValidationError, RouterInventoryError, UserCancelledError
from bgp.validation import coletar_sessao, perguntar_preview, perguntar_validacao_irr, confirmar_sessao, decidir_aplicar_quando_existe
from bgp.commands import build_huawei_commands, preview_commands
from bgp.irr import validar_asn_prefixo
from bgp.router_io import ler_routers_txt, escolher_roteadores
from bgp.connector import executar_bgp
from bgp.report import gerar_relatorio

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    try:
        session = coletar_sessao()
        cmds = build_huawei_commands(session)

        if perguntar_preview():
            preview_commands(cmds)

        if perguntar_validacao_irr():
            try:
                validar_asn_prefixo(session.prefixes_ipv4 + session.prefixes_ipv6, session.neighbor_as)
            except IrrValidationError as e:
                logger.error(f"Validação IRR falhou: {e}")
                sys.exit(1)

        confirmar_sessao(session)

        try:
            routers_all = ler_routers_txt()
        except RouterInventoryError as e:
            logger.error(str(e))
            sys.exit(1)

        routers = escolher_roteadores(routers_all)
        resultados = executar_bgp(routers, session, cmds, decidir_aplicar_quando_existe)

        routers_txt_path = str(Path(ARQUIVO_ROUTERS).resolve())
        pdf_path, pdf_hash, routers_hash = gerar_relatorio(resultados, routers_txt_path)

        print(f"\n✅ PDF gerado: {pdf_path}")
        print(f"✅ SHA256 do PDF: {pdf_hash}")
        print(f"✅ SHA256 do routers.txt: {routers_hash}")
        print(f"✅ Backups em: {BACKUP_DIR.resolve()}\n")

    except UserCancelledError as e:
        logger.info(str(e))
        sys.exit(0)
    except KeyboardInterrupt:
        print("\nOperação interrompida pelo usuário.")
        sys.exit(0)
    except BgpAutomacaoError as e:
        logger.error(str(e))
        sys.exit(1)


if __name__ == "__main__":
    main()
