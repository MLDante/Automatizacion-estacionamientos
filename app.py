"""Aplicación FastAPI principal con endpoints de autenticación y transacciones.

Cada función incluye comentarios explicando su propósito dentro del flujo 2PC.
"""

from fastapi import FastAPI, Depends, HTTPException, status, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Optional, List
from models import User, TransactionLog
from database import init_db, DBSession
from security import hash_password, verify_password, create_token, decode_token
from config import get_settings
from transaction import TransactionService
import json
import requests

settings = get_settings()
app = FastAPI(title="Distributed 2PC API", version="0.1.0")
security = HTTPBearer()

# ---------------------------- Schemas ----------------------------
class RegisterPayload(BaseModel):
    """Payload para registro de usuarios nuevos (solo admin)."""
    username: str
    password: str
    role: str = "user"

class LoginPayload(BaseModel):
    """Payload para inicio de sesión y obtención de JWT."""
    username: str
    password: str

class TransferPayload(BaseModel):
    """Payload para solicitar una transferencia distribuida."""
    amount: float
    from_account: int
    to_account: int

# ----------------------- Auth Dependencies -----------------------

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Obtiene el usuario autenticado a partir del token JWT o lanza 401."""
    token = credentials.credentials
    data = decode_token(token)
    if not data:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    username = data.get('sub')
    with DBSession() as s:
        user = s.query(User).filter(User.username == username).first()
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        return user


def require_role(role: str):
    """Genera dependencia que valida que el usuario tenga el rol requerido."""
    def checker(user: User = Depends(get_current_user)):
        if user.role != role:
            raise HTTPException(status_code=403, detail="Forbidden: insufficient role")
        return user
    return checker

# ------------------------- Startup Event -------------------------
@app.on_event("startup")
def on_startup():
    """Inicializa la base de datos y crea usuario admin por defecto si falta."""
    init_db()
    with DBSession() as s:
        admin = s.query(User).filter(User.username == 'admin').first()
        if not admin:
            s.add(User(username='admin', password_hash=hash_password('admin'), role='admin'))
            s.commit()

# --------------------------- Auth Routes -------------------------
@app.post('/auth/register')
def register(payload: RegisterPayload, admin: User = Depends(require_role('admin'))):
    """Registra un nuevo usuario (solo accesible para rol admin)."""
    with DBSession() as s:
        existing = s.query(User).filter(User.username == payload.username).first()
        if existing:
            raise HTTPException(status_code=400, detail="Username already exists")
        u = User(username=payload.username, password_hash=hash_password(payload.password), role=payload.role)
        s.add(u)
        s.commit()
        s.refresh(u)
        return {"id": u.id, "username": u.username, "role": u.role}

@app.post('/auth/login')
def login(payload: LoginPayload):
    """Autentica usuario y devuelve token JWT para futuras peticiones."""
    with DBSession() as s:
        user = s.query(User).filter(User.username == payload.username).first()
        if not user or not verify_password(payload.password, user.password_hash):
            raise HTTPException(status_code=401, detail="Invalid credentials")
        token = create_token(user.username, user.role)
        return {"access_token": token, "token_type": "bearer"}

# ----------------------- Transaction Endpoints -------------------
@app.post('/transfer')
def transfer(payload: TransferPayload, user: User = Depends(get_current_user)):
    """Inicia una transferencia distribuida aplicando protocolo 2PC."""
    if payload.amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be positive")
    log = TransactionService.start_transfer(payload.amount, payload.from_account, payload.to_account)
    return {"tx_id": log.tx_id, "status": log.status, "participants": json.loads(log.participants)}

@app.get('/transactions/{tx_id}')
def get_tx(tx_id: str, user: User = Depends(get_current_user)):
    """Recupera detalle de una transacción específica por su tx_id."""
    log = TransactionService.get_transaction(tx_id)
    if not log:
        raise HTTPException(status_code=404, detail="Not found")
    return {"tx_id": log.tx_id, "status": log.status, "participants": json.loads(log.participants)}

@app.get('/transactions')
def list_tx(limit: int = 50, user: User = Depends(get_current_user)):
    """Lista transacciones recientes mostrando estado general."""
    rows = TransactionService.list_transactions(limit)
    return [{"tx_id": r.tx_id, "status": r.status} for r in rows]

@app.post('/admin/reconcile')
def reconcile(admin: User = Depends(require_role('admin'))):
    """Ejecuta reconciliación para abortar transacciones PREPARED antiguas."""
    actions = TransactionService.reconcile_stuck()
    return {"performed": actions}

# -------------------------- Utility ------------------------------
@app.get('/health')
def health():
    """Verificación básica de salud y número de participantes configurados."""
    return {
        "status": "ok",
        "participants_configured": len(settings.participants)
    }

# -------------------------- Balance ------------------------------
@app.get('/balance/{account_id}')
def balance(account_id: int, user: User = Depends(get_current_user)):
    """Consulta de balance (placeholder) intentando alcanzar algún participante.

    Regresa advertencia si los servicios aún no implementan endpoint real.
    """
    errors = []
    for p in settings.participants:
        try:
            resp = requests.get(f"{p['url']}/health", timeout=settings.request_timeout)
            if resp.status_code == 200:
                return {"account_id": account_id, "source": p['name'], "reachable": True, "warning": "Balance endpoint not implemented on participant"}
        except Exception as e:
            errors.append({"participant": p['name'], "error": str(e)})
    raise HTTPException(status_code=503, detail={"message": "No participant reachable", "errors": errors})
