# Distributed 2PC API (Carpeta: API final)

Este módulo agrega una API coordinadora y de autenticación para un sistema distribuido con un protocolo de dos fases (2PC), roles y persistencia de decisiones.

## Características
- Coordinador 2PC: inicia transferencias entre participantes (bancos) vía endpoints `/prepare` / `/commit` / `/rollback` de cada servicio.
- Persistencia de transacciones: tabla `TransactionLog` con estados `PREPARED`, `COMMITTED`, `ABORTED`.
- Seguridad: Registro, login y JWT con roles (`admin`, `user`).
- Reconciliación: Endpoint `/admin/reconcile` aborta transacciones PREPARED estancadas.
- Configurable por variables de entorno.

## Variables de Entorno Clave
```
TX_DB_URL=sqlite:///./transactions.db    # URL base de datos interna
JWT_SECRET=super-secreto                 # Clave para firmar JWT
BANK_PARTICIPANTS="bank_a|http://bank_a_api:8001|debit,bank_b|http://bank_b_api:8002|credit,bank_c|http://bank_c_api:8003|mirror"
REQUEST_TIMEOUT=3                        # Timeout por request
REQUEST_RETRIES=2                        # Reintentos en fase prepare
RECONCILE_INTERVAL_SEC=60                # Intervalo para reconciliaciones automáticas (extensible)
```

## Instalación
```bash
pip install -r requirements.txt
uvicorn app:app --reload --port 8100
```

## Flujo de Transferencia (/transfer)
1. Fase PREPARE: Envia JSON adaptado por rol a cada participante.
2. Si todos responden `READY`, se ejecuta Fase COMMIT.
3. Si alguno falla se hace rollback (mejor esfuerzo) y se marca `ABORTED`.

## Endpoints Principales
- `POST /auth/login` / `POST /auth/register`
- `POST /transfer`
- `GET /transactions` / `GET /transactions/{tx_id}`
- `POST /admin/reconcile`
- `GET /balance/{account_id}` (placeholder; requiere implementar en bancos para obtener saldo real)

## Extensiones Sugeridas
- Añadir tabla para estados por participante más detallados.
- Implementar endpoint `/balance` real en servicios banco para consulta consistente.
- Añadir mecanismo de background para reconciliación periódica (scheduler / Celery / APScheduler).
- Integrar tercer banco real y ajustar `BANK_PARTICIPANTS`.

## Notas
Esta implementación no modifica los servicios existentes; depende de que expongan `/prepare`, `/commit`, `/rollback`. Para cumplimiento completo de ACID se debería:
- Persistir estado PREPARED en cada banco antes de responder READY.
- Reintroducir transacciones en caso de fallo usando un commit log duradero.

## Roles
- `admin`: Puede registrar usuarios y ejecutar reconciliaciones.
- `user`: Puede iniciar transferencias y consultar transacciones.

## Ejemplo de Uso (curl)
```bash
# Login admin (usuario se crea automáticamente si no existe)
curl -X POST http://localhost:8100/auth/login -H 'Content-Type: application/json' -d '{"username":"admin","password":"admin"}'
# Usar token para transferir
curl -X POST http://localhost:8100/transfer -H 'Authorization: Bearer <TOKEN>' -H 'Content-Type: application/json' -d '{"amount":50,"from_account":1,"to_account":2}'
```
