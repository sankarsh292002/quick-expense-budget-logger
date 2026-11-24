"""
auth.py - authentication: password hashing, login tokens and the current user.

Owner: Member A (API)

AuthService groups everything about identity in one class (slide 67):
    hash_password()     -> store only a salted hash, never the password
    verify_password()   -> compare an entered password with the stored hash
    create_token()      -> JWT (header.payload.signature) with "sub" = user_id and "exp"
    read_token()        -> user_id if the JWT signature is valid and it has not expired
A JWT is SIGNED, not encrypted: anyone can read the payload, nobody can change it
without the SECRET_KEY. So we never put passwords or secrets inside it (slide 58).
get_current_user() is the FastAPI dependency every protected route uses:
missing, invalid or expired token -> 401 Unauthorized.
"""
import hashlib  # algoritmos de hash: PBKDF2 y SHA-256
import hmac  # comparación de textos en tiempo constante (compare_digest)
import os  # lee variables de entorno, como SECRET_KEY desde .env
import secrets  # genera bytes aleatorios seguros para la "sal"
from datetime import datetime, timedelta, timezone  # fechas y duraciones, para la expiración "exp" del JWT

import jwt  # librería PyJWT: crea y verifica tokens JWT
from fastapi import Depends, HTTPException, status  # inyección de dependencias, errores HTTP y códigos de estado
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer  # lee la cabecera "Authorization: Bearer <token>"
from sqlalchemy.orm import Session  # tipo de la sesión de base de datos

from . import models  # modelos ORM; aquí usamos models.User
from .database import get_db  # dependencia que abre y cierra una sesión por petición


class AuthService:  # clase que agrupa toda la lógica de autenticación
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-secret-change-me-in-env-file-0123456789abcdef")  # clave secreta para firmar tokens, leída de .env (mínimo 32 caracteres para HS256)
    ALGORITHM = "HS256"  # algoritmo de firma del JWT: HMAC con SHA-256 y la SECRET_KEY
    TOKEN_LIFETIME = timedelta(hours=24)  # el token vale 24 horas
    PBKDF2_ROUNDS = 200_000  # repeticiones del hash: hace lento adivinar contraseñas

    @staticmethod  # método que no necesita un objeto: se llama AuthService.hash_password(...)
    def hash_password(password: str) -> str:  # recibe la contraseña en texto y devuelve el hash a guardar
        salt = secrets.token_bytes(16)  # 16 bytes aleatorios: dos usuarios con la misma contraseña tendrán hashes distintos
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, AuthService.PBKDF2_ROUNDS)  # calcula el hash PBKDF2-SHA256
        return f"{salt.hex()}${digest.hex()}"  # guarda "sal$hash" en hexadecimal, en una sola columna

    @staticmethod  # método estático
    def verify_password(password: str, stored: str) -> bool:  # True si la contraseña ingresada coincide con el hash guardado
        salt_hex, digest_hex = stored.split("$")  # separa la sal y el hash guardados
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), AuthService.PBKDF2_ROUNDS)  # recalcula el hash con la MISMA sal
        return hmac.compare_digest(digest.hex(), digest_hex)  # compara en tiempo constante (evita ataques por tiempo); el hash nunca se "descifra"

    @staticmethod  # método estático
    def create_token(user_id: int) -> str:  # crea el JWT que recibe el cliente al registrarse o hacer login
        expires = datetime.now(timezone.utc) + AuthService.TOKEN_LIFETIME  # momento de expiración: ahora (UTC) + 24 h
        payload = {"sub": str(user_id), "exp": expires}  # contenido del JWT: "sub" = id del usuario (como texto), "exp" = expiración
        return jwt.encode(payload, AuthService.SECRET_KEY, algorithm=AuthService.ALGORITHM)  # codifica y firma: "header.payload.signature"

    @staticmethod  # método estático
    def read_token(token: str) -> int | None:  # devuelve el user_id si el JWT es válido; si no, None
        try:  # jwt.decode lanza una excepción si algo está mal
            payload = jwt.decode(token, AuthService.SECRET_KEY, algorithms=[AuthService.ALGORITHM])  # verifica la firma y que "exp" no haya pasado
            return int(payload["sub"])  # token válido -> devuelve el id del usuario guardado en "sub"
        except (jwt.PyJWTError, KeyError, ValueError):  # firma alterada, token vencido, mal formado o sin "sub"
            return None  # cualquiera de esos casos -> token inválido


bearer_scheme = HTTPBearer(auto_error=False)  # extrae el token de "Authorization: Bearer ..."; sin error automático para dar nuestro propio 401


def get_current_user(  # dependencia que usa toda ruta protegida
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),  # FastAPI le pasa el token de la cabecera (o None)
    db: Session = Depends(get_db),  # FastAPI le pasa una sesión de base de datos
) -> models.User:  # devuelve el usuario que hizo la petición
    not_logged_in = HTTPException(  # prepara el error 401 que usaremos en cada caso de fallo
        status_code=status.HTTP_401_UNAUTHORIZED,  # 401 = no autenticado
        detail="Not logged in or session expired",  # mensaje que verá el cliente
        headers={"WWW-Authenticate": "Bearer"},  # indica al cliente que debe enviar un token Bearer
    )  # fin del objeto de error
    if credentials is None:  # no vino cabecera Authorization
        raise not_logged_in  # -> 401
    user_id = AuthService.read_token(credentials.credentials)  # valida el token y obtiene el user_id
    if user_id is None:  # token inválido o vencido
        raise not_logged_in  # -> 401
    user = db.get(models.User, user_id)  # busca el usuario en PostgreSQL por su clave primaria
    if user is None:  # el usuario ya no existe
        raise not_logged_in  # -> 401
    return user  # usuario autenticado; la ruta lo recibe como parámetro
