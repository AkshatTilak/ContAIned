"""Abstract base class for all async external database connectors (Task 12).

Each concrete driver must implement:
- test_connection()     — verify TCP/auth connectivity.
- execute_query()       — run a parametrized SELECT returning up to `max_rows` dicts.
- get_schema_metadata() — return table / collection schema summary.

Safety invariants enforced across all implementations:
- `is_read_only=True` → reject DDL/DML keywords and enforce READ ONLY transactions.
- Row cap hard-coded at `settings.MAX_EXTERNAL_DB_ROWS` (default 1,000).
- `statement_timeout_ms` enforced at driver level.
"""

import re
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from common.config.settings import settings

logger = logging.getLogger("common.clients.db_connectors.base")

# DDL / DML keyword guard — reject statements containing these at word boundaries
_DML_PATTERN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|TRUNCATE|REPLACE|MERGE|GRANT|REVOKE)\b",
    re.IGNORECASE,
)
# Allow at most 1 statement separator (semicolon) at the end
_MULTI_STMT_PATTERN = re.compile(r";.+", re.DOTALL)


def _check_query_safety(query: str, is_read_only: bool) -> None:
    """Raise ValueError if `query` violates read-only guardrails.

    Blocks:
    - Multiple statements (two or more semicolons with content after the first).
    - DDL / DML keywords when `is_read_only` is True.
    """
    stripped = query.strip()
    if _MULTI_STMT_PATTERN.search(stripped.rstrip(";")):
        raise ValueError("Multi-statement queries are not allowed.")
    if is_read_only and _DML_PATTERN.search(stripped):
        raise ValueError(
            "DDL/DML statements are prohibited on read-only credentials. "
            "Only SELECT-like queries are permitted."
        )


class BaseDatabaseConnector(ABC):
    """Abstract async external database connector.

    Parameters
    ----------
    credential_id : str
        The ExternalCredential row ID this connector represents.
    config : dict
        Decrypted credential payload merged with connection metadata.
        Expected keys: host, port, database_name, username, password,
        is_read_only, max_connections, statement_timeout_ms.
    """

    MAX_ROWS: int = getattr(settings, "MAX_EXTERNAL_DB_ROWS", 1_000)
    DEFAULT_TIMEOUT_S: int = 30

    def __init__(self, credential_id: str, config: Dict[str, Any]) -> None:
        self.credential_id = credential_id
        self.config = config
        self.is_read_only: bool = config.get("is_read_only", True)
        self._connected = False

    # ------------------------------------------------------------------
    # Abstract interface
    # ------------------------------------------------------------------

    @abstractmethod
    async def connect(self) -> None:
        """Initialise the underlying connection pool."""
        ...

    @abstractmethod
    async def close(self) -> None:
        """Release the underlying connection pool."""
        ...

    @abstractmethod
    async def test_connection(self) -> bool:
        """Return True if a ping/health-check query succeeds."""
        ...

    @abstractmethod
    async def execute_query(
        self,
        query: str,
        params: Optional[Dict[str, Any]] = None,
        timeout_s: int = DEFAULT_TIMEOUT_S,
        max_rows: int = MAX_ROWS,
    ) -> List[Dict[str, Any]]:
        """Execute a query and return at most `max_rows` result rows as dicts."""
        ...

    @abstractmethod
    async def get_schema_metadata(self) -> Dict[str, Any]:
        """Return a summary dict describing tables / collections / keys."""
        ...

    async def store_record(
        self,
        target_table: str,
        record: Dict[str, Any],
        operation: str = "insert",
    ) -> Dict[str, Any]:
        """Persist a record into the target table/collection.

        Default implementation refuses writes on read-only credentials.
        Concrete drivers override this to perform insert/upsert/append.
        """
        if self.is_read_only:
            raise ValueError(
                "DBStoreNode write operation refused: credential is read-only."
            )
        raise NotImplementedError(
            f"{type(self).__name__} does not implement store_record()"
        )

    # ------------------------------------------------------------------
    # Shared safety helpers
    # ------------------------------------------------------------------

    def _assert_safe(self, query: str) -> None:
        """Apply read-only guardrails. Raises ValueError on violation."""
        _check_query_safety(query, self.is_read_only)

    def _cap_rows(self, rows: List[Dict[str, Any]], max_rows: int) -> List[Dict[str, Any]]:
        """Truncate rows to the lesser of `max_rows` and `self.MAX_ROWS`."""
        limit = min(max_rows, self.MAX_ROWS)
        return rows[:limit]
