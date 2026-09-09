"""OracleError base class and error matrix (PRD-002 §12).

Exit codes: 0 ok · 2 ingest/validation · 3 model/seg · 4 rag · 5 synth/audit · 6 vault.
"""

from __future__ import annotations


class OracleError(Exception):
    """Base error for all ORACLE failures. Carries machine code + CLI exit code."""

    code: str = "E-ORC-000"
    exit_code: int = 1

    def __init__(
        self,
        message: str,
        *,
        detail: str | None = None,
        code: str | None = None,
        exit_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.detail = detail
        if code is not None:
            self.code = code
        if exit_code is not None:
            self.exit_code = exit_code

    def to_dict(self) -> dict[str, str | None]:
        return {"code": self.code, "message": self.message, "detail": self.detail}


class IngestError(OracleError):
    code = "E-ING-000"
    exit_code = 2


def e_ing_001(message: str, **kw: str) -> IngestError:
    return IngestError(message, code="E-ING-001", **kw)


def e_ing_002(message: str, **kw: str) -> IngestError:
    return IngestError(message, code="E-ING-002", **kw)


def e_ing_003(message: str, **kw: str) -> IngestError:
    return IngestError(message, code="E-ING-003", **kw)


def e_ing_004(message: str, **kw: str) -> IngestError:
    return IngestError(message, code="E-ING-004", **kw)


class SegError(OracleError):
    code = "E-SEG-000"
    exit_code = 3


class RagError(OracleError):
    code = "E-RAG-000"
    exit_code = 4


class SynthError(OracleError):
    code = "E-SYN-000"
    exit_code = 5


class VaultError(OracleError):
    code = "E-VLT-000"
    exit_code = 6
