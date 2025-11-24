"""Módulo de configuración de la API distribuida.

Proporciona lectura de variables de entorno y parsing de la lista de participantes
que intervienen en las transacciones 2PC.

Formato esperado en BANK_PARTICIPANTS:
  "nombre|url|rol,nombre|url|rol,..." donde rol ∈ {debit, credit, mirror}.
"""

import os
from functools import lru_cache
from typing import List, Dict

# parse_participants: Convierte la cadena cruda de participantes en una lista
# de diccionarios con nombre, url y rol.
def parse_participants(raw: str) -> List[Dict[str, str]]:
    participants = []
    if not raw:
        return participants
    for item in raw.split(','):
        parts = item.split('|')
        if len(parts) >= 3:
            participants.append({
                'name': parts[0].strip(),
                'url': parts[1].strip(),
                'role': parts[2].strip()
            })
    return participants

# get_settings: Devuelve (cacheado) la instancia única de Settings.
@lru_cache
def get_settings():
    return Settings()

class Settings:
    """Agrupa todos los parámetros de configuración usados en la aplicación.

    Se inicializa leyendo variables de entorno. Incluye timeouts, reintentos
    y lista de participantes para 2PC.
    """
    def __init__(self):
        self.database_url = os.getenv('TX_DB_URL', 'sqlite:///./transactions.db')
        self.jwt_secret = os.getenv('JWT_SECRET', 'dev-secret-change')
        self.jwt_algorithm = os.getenv('JWT_ALG', 'HS256')
        self.jwt_exp_minutes = int(os.getenv('JWT_EXP_MIN', '60'))
        raw_participants = os.getenv('BANK_PARTICIPANTS', '')
        self.participants = parse_participants(raw_participants)
        # Parámetros de red
        self.request_timeout = float(os.getenv('REQUEST_TIMEOUT', '3'))
        self.max_retries = int(os.getenv('REQUEST_RETRIES', '2'))
        self.reconcile_interval = int(os.getenv('RECONCILE_INTERVAL_SEC', '60'))
