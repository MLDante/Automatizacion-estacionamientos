"""Módulo de acceso a la base de datos.

Define el motor y utilidades de sesión para realizar operaciones CRUD.
"""

from sqlmodel import SQLModel, create_engine, Session
from config import get_settings

settings = get_settings()
engine = create_engine(settings.database_url, echo=False)

# init_db: Crea todas las tablas definidas en los modelos si no existen.
def init_db():
    SQLModel.metadata.create_all(engine)

class DBSession:
    """Context manager para manejar sesiones.

    Al salir del contexto realiza rollback si hubo excepción y cierra la sesión.
    """
    def __enter__(self):
        self.session = Session(engine)
        return self.session

    def __exit__(self, exc_type, exc, tb):
        if exc:
            self.session.rollback()
        self.session.close()
