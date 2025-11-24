"""Funciones de seguridad: hashing de contraseñas y manejo de JWT.

Se utiliza bcrypt vía passlib para almacenar contraseñas y PyJWT para tokens.
"""

from datetime import datetime, timedelta
from passlib.context import CryptContext
import jwt
from config import get_settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
settings = get_settings()

# hash_password: Genera hash bcrypt de una contraseña en texto plano.
def hash_password(password: str) -> str:
    return pwd_context.hash(password)

# verify_password: Verifica si la contraseña suministrada coincide con el hash.
def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)

# create_token: Crea un JWT con sujeto y rol, expirando en minutos configurados.
def create_token(sub: str, role: str):
    exp = datetime.utcnow() + timedelta(minutes=settings.jwt_exp_minutes)
    payload = {"sub": sub, "role": role, "exp": exp}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)

# decode_token: Decodifica el JWT y retorna payload o None si inválido/expirado.
def decode_token(token: str):
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError:
        return None
