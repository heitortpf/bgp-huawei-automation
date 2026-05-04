from dataclasses import dataclass, field


@dataclass
class RouterConfig:
    host: str
    username: str
    password: str
    port: int


@dataclass
class BgpSessionConfig:
    local_as: int
    neighbor_ip: str
    neighbor_as: int
    nome_cliente: str
    prefixes_ipv4: list[str] = field(default_factory=list)
    prefixes_ipv6: list[str] = field(default_factory=list)

    @property
    def nome_prefix_ipv4(self) -> str:
        return f"{self.nome_cliente}-IPv4"

    @property
    def rp_imp_v4(self) -> str:
        return f"CLI-BGP-{self.nome_cliente}-IPv4-IMPORT"

    @property
    def rp_exp_v4(self) -> str:
        return f"CLI-BGP-{self.nome_cliente}-IPv4-EXPORT"

    @property
    def nome_prefix_ipv6(self) -> str:
        return f"{self.nome_cliente}-IPv6"

    @property
    def rp_imp_v6(self) -> str:
        return f"CLI-BGP-{self.nome_cliente}-IPv6-IMPORT"

    @property
    def rp_exp_v6(self) -> str:
        return f"CLI-BGP-{self.nome_cliente}-IPv6-EXPORT"


@dataclass
class ExecutionResult:
    host: str
    status: str
    duracao_s: float
    backup_path: str = "(não gerado)"
    backup_sha256: str = "-"
    backup_size: str = "-"
    display_bgp_peer: str = "(não coletado)"
    bgp_display_this: str = "(não coletado)"
    recorte_cliente: str = "(não coletado)"
