"""Modelos de datos persistentes.

Incluye usuarios, log de transacciones y caché de balances para posibles
consultas tolerantes a fallos.
"""

from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field

class User(SQLModel, table=True):
    """Representa un usuario autenticable con rol.

    Campos:
      username: Nombre único.
      password_hash: Hash seguro de la contraseña.
      role: user | admin.
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(index=True)
    password_hash: str
    role: str = Field(default='user', index=True)

class TransactionLog(SQLModel, table=True):
    """Registro de cada transacción 2PC.

    Guarda el tx_id, estado final y snapshot JSON de estados de participantes.
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    tx_id: str = Field(index=True)
    status: str  # PREPARED | COMMITTED | ABORTED | ERROR
    participants: str  # JSON con estados de cada participante
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class BalanceCache(SQLModel, table=True):
    """Caché de balances para consultas rápidas o fallback.

    Puede usarse para responder /balance cuando los participantes estén caídos.
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    account_id: int = Field(index=True)
    last_known_balance: float
    source: str
    updated_at: datetime = Field(default_factory=datetime.utcnow)
