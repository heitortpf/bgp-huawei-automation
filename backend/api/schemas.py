import ipaddress
from pydantic import BaseModel, field_validator


class BgpSessionRequest(BaseModel):
    local_as: int
    neighbor_ip: str
    neighbor_as: int
    nome_cliente: str
    prefixes_ipv4: list[str] = []
    prefixes_ipv6: list[str] = []

    @field_validator("neighbor_ip")
    @classmethod
    def validate_ip(cls, v: str) -> str:
        try:
            ipaddress.ip_address(v)
        except ValueError:
            raise ValueError(f"IP inválido: {v!r}")
        return v

    @field_validator("prefixes_ipv4")
    @classmethod
    def validate_ipv4_prefix(cls, v: list[str]) -> list[str]:
        for prefix in v:
            try:
                ipaddress.IPv4Network(prefix, strict=False)
            except ValueError:
                raise ValueError(f"Prefixo IPv4 inválido: {prefix!r}")
        return v

    @field_validator("prefixes_ipv6")
    @classmethod
    def validate_ipv6_prefix(cls, v: list[str]) -> list[str]:
        for prefix in v:
            try:
                ipaddress.IPv6Network(prefix, strict=False)
            except ValueError:
                raise ValueError(f"Prefixo IPv6 inválido: {prefix!r}")
        return v


class PreviewRequest(BaseModel):
    sessao: BgpSessionRequest


class PreviewResponse(BaseModel):
    comandos: list[str]


class ValidarIrrRequest(BaseModel):
    prefixos: list[str]
    asn_peer: int


class ValidarIrrResponse(BaseModel):
    ok: bool


class AplicarRequest(BaseModel):
    sessao: BgpSessionRequest
    roteadores: list[str] | None = None
    aplicar_se_existir: bool = False
    gerar_relatorio: bool = True


class ExecutionResultResponse(BaseModel):
    host: str
    status: str
    duracao_s: float
    backup_sha256: str
    display_bgp_peer: str
    bgp_display_this: str
    recorte_cliente: str


class AplicarResponse(BaseModel):
    resultados: list[ExecutionResultResponse]
    relatorio_nome: str | None = None
    relatorio_sha256: str | None = None


class RouterIn(BaseModel):
    host: str
    username: str
    password: str
    port: int = 22


class RouterOut(BaseModel):
    host: str
    username: str
    port: int


class PrefixosResponse(BaseModel):
    ipv4: list[str]
    ipv6: list[str]


class HistoricoItemResponse(BaseModel):
    id: int
    timestamp: str
    nome_cliente: str
    neighbor_ip: str
    local_as: int
    neighbor_as: int
    roteadores: list[str]
    resultados: list[ExecutionResultResponse]
    relatorio_nome: str | None
