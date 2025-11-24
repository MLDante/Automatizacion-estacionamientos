"""Abstracciones para ejecutar el protocolo de dos fases (2PC).

Incluye el estado de cada participante y la lógica de PREPARE, COMMIT y ROLLBACK
con reintentos y manejo de errores básicos.
"""

import json
import time
import uuid
from typing import Dict, List
import requests
from config import get_settings

settings = get_settings()

class ParticipantState:
    """Estado individual de un participante en una transacción.

    Guarda rol, URL y resultados de prepare/commit, además de errores.
    """
    def __init__(self, name: str, role: str, url: str):
        self.name = name
        self.role = role
        self.url = url.rstrip('/')
        self.prepare_status = None  # READY | ABORT | ERROR | UNREACHABLE
        self.commit_status = None   # COMMITTED | ABORT | ERROR | SKIPPED
        self.error: str | None = None

    # to_dict: Serializa el estado del participante para logging/almacenamiento.
    def to_dict(self):
        return {
            'name': self.name,
            'role': self.role,
            'url': self.url,
            'prepare_status': self.prepare_status,
            'commit_status': self.commit_status,
            'error': self.error,
        }

class TwoPhaseCommit:
    """Orquesta una transacción 2PC sobre un conjunto de participantes."""
    def __init__(self, participants_cfg: List[Dict[str, str]]):
        self.tx_id = str(uuid.uuid4())
        self.participants = [ParticipantState(p['name'], p['role'], p['url']) for p in participants_cfg]

    # _prepare_payload: Construye payload específico por rol para fase PREPARE.
    def _prepare_payload(self, p: ParticipantState, amount: float, from_account: int, to_account: int):
        if p.role == 'debit':
            return {'tx_id': self.tx_id, 'amount': amount, 'from_account': from_account}
        if p.role == 'credit':
            return {'tx_id': self.tx_id, 'amount': amount, 'to_account': to_account}
        # mirror: replica info completa para potencial sincronización.
        return {'tx_id': self.tx_id, 'amount': amount, 'from_account': from_account, 'to_account': to_account}

    # _commit_payload: Reutiliza el mismo payload que PREPARE (puede extenderse si difieren).
    def _commit_payload(self, p: ParticipantState, amount: float, from_account: int, to_account: int):
        return self._prepare_payload(p, amount, from_account, to_account)

    # phase_prepare: Ejecuta la fase PREPARE contra todos los participantes.
    # Retorna True si todos responden READY, False si alguno falla/ABORT.
    def phase_prepare(self, amount: float, from_account: int, to_account: int):
        for p in self.participants:
            payload = self._prepare_payload(p, amount, from_account, to_account)
            for attempt in range(settings.max_retries + 1):
                try:
                    resp = requests.post(f"{p.url}/prepare", json=payload, timeout=settings.request_timeout)
                    data = resp.json()
                    p.prepare_status = data.get('status', 'ERROR')
                    break
                except Exception as e:
                    p.prepare_status = 'UNREACHABLE'
                    p.error = str(e)
                    time.sleep(0.2 * (attempt + 1))
            if p.prepare_status not in ('READY',):
                # Abort temprano si algún participante no está listo.
                return False
        return True

    # phase_commit: Envía COMMIT a todos los participantes READY.
    # Si falla alguno, dispara phase_rollback y retorna False.
    def phase_commit(self, amount: float, from_account: int, to_account: int):
        for p in self.participants:
            if p.prepare_status != 'READY':
                p.commit_status = 'SKIPPED'
                continue
            payload = self._commit_payload(p, amount, from_account, to_account)
            try:
                resp = requests.post(f"{p.url}/commit", json=payload, timeout=settings.request_timeout)
                p.commit_status = resp.json().get('status', 'ERROR')
            except Exception as e:
                p.commit_status = 'ERROR'
                p.error = str(e)
        failed = [p for p in self.participants if p.commit_status not in ('COMMITTED', 'SKIPPED')]
        if failed:
            self.phase_rollback(amount, from_account, to_account)
            return False
        return True

    # phase_rollback: Mejor esfuerzo para revertir participantes que estaban READY.
    def phase_rollback(self, amount: float, from_account: int, to_account: int):
        for p in self.participants:
            if p.prepare_status == 'READY':
                try:
                    requests.post(f"{p.url}/rollback", json={'tx_id': self.tx_id}, timeout=settings.request_timeout)
                except Exception as e:
                    p.error = (p.error or '') + f"; rollback_err={e}" if p.error else f"rollback_err={e}"

    # serialize: Devuelve JSON con lista de estados de participantes.
    def serialize(self):
        return json.dumps([p.to_dict() for p in self.participants])
