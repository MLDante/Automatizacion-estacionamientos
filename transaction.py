"""Servicio de alto nivel para operaciones sobre transacciones 2PC."""

from typing import Optional
from sqlmodel import select
from models import TransactionLog
from database import DBSession
from participant import TwoPhaseCommit
from config import get_settings
from datetime import datetime, timedelta

settings = get_settings()

class TransactionService:
    """Agrupa lógica de inicio, consulta y reconciliación de transacciones."""
    @staticmethod
    def start_transfer(amount: float, from_account: int, to_account: int):
        """Inicia una transferencia 2PC.

        Ejecuta fase PREPARE y si todos READY continúa con COMMIT. Registra
        el resultado (COMMITTED o ABORTED) en el log.
        """
        tpc = TwoPhaseCommit(settings.participants)
        prepared_ok = tpc.phase_prepare(amount, from_account, to_account)
        status = 'PREPARED' if prepared_ok else 'ABORTED'
        if prepared_ok:
            committed_ok = tpc.phase_commit(amount, from_account, to_account)
            status = 'COMMITTED' if committed_ok else 'ABORTED'
        with DBSession() as s:
            log = TransactionLog(tx_id=tpc.tx_id, status=status, participants=tpc.serialize())
            s.add(log)
            s.commit()
            s.refresh(log)
        return log

    @staticmethod
    def get_transaction(tx_id: str) -> Optional[TransactionLog]:
        """Recupera una transacción por su tx_id o None si no existe."""
        with DBSession() as s:
            statement = select(TransactionLog).where(TransactionLog.tx_id == tx_id)
            result = s.exec(statement).first()
            return result

    @staticmethod
    def reconcile_stuck(age_minutes: int = 5):
        """Marca como ABORTED transacciones PREPARED que exceden el umbral de edad.

        Proporciona una acción de limpieza para transacciones estancadas.
        """
        cutoff = datetime.utcnow() - timedelta(minutes=age_minutes)
        with DBSession() as s:
            statement = select(TransactionLog).where(TransactionLog.status == 'PREPARED')
            stuck = s.exec(statement).all()
            actions = []
            for log in stuck:
                if log.created_at < cutoff:
                    log.status = 'ABORTED'
                    log.updated_at = datetime.utcnow()
                    actions.append({'tx_id': log.tx_id, 'action': 'ABORTED'})
            s.commit()
        return actions

    @staticmethod
    def list_transactions(limit: int = 50):
        """Lista transacciones recientes limitadas por 'limit'."""
        with DBSession() as s:
            statement = select(TransactionLog).order_by(TransactionLog.id.desc()).limit(limit)
            return s.exec(statement).all()
