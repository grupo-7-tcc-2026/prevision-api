import base64
import binascii
import hashlib
import hmac
import io
import logging
import os
import secrets
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal

import mysql.connector
from dotenv import load_dotenv
from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from mysql.connector import IntegrityError
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, Field

load_dotenv(Path(__file__).with_name(".env"))
router = APIRouter()
logger = logging.getLogger(__name__)
MAX_IMAGE_BYTES = 5 * 1024 * 1024
Image.MAX_IMAGE_PIXELS = 25_000_000


@contextmanager
def database():
    required = ("MYSQL_HOST", "MYSQL_DATABASE", "MYSQL_USER")
    if any(not os.environ.get(key) for key in required) or "MYSQL_PASSWORD" not in os.environ:
        logger.error("MySQL configuration is incomplete")
        raise HTTPException(status_code=503, detail="Banco de dados não configurado.")
    try:
        connection = mysql.connector.connect(
            host=os.environ["MYSQL_HOST"],
            port=int(os.environ.get("MYSQL_PORT", "3306")),
            database=os.environ["MYSQL_DATABASE"],
            user=os.environ["MYSQL_USER"],
            password=os.environ["MYSQL_PASSWORD"],
            connection_timeout=5,
        )
    except (mysql.connector.Error, ValueError):
        logger.exception("Could not connect to MySQL")
        raise HTTPException(status_code=503, detail="Banco de dados indisponível.")
    try:
        yield connection
    finally:
        connection.close()


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    derived = hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1)
    return f"scrypt${salt.hex()}${derived.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algorithm, salt, expected = stored.split("$")
        if algorithm != "scrypt":
            return False
        derived = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1)
        return hmac.compare_digest(derived.hex(), expected)
    except (ValueError, TypeError):
        logger.error("Invalid stored password hash")
        return False


class RegisterRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=128)


class ReportRequest(BaseModel):
    region: Literal["Centro", "Norte", "Sul", "Leste", "Oeste"]
    address: str = Field(min_length=1, max_length=255)
    image: str = Field(max_length=7_000_000)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def current_user(authorization: str | None = Header(default=None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Faça login para continuar.")
    token = authorization[7:]
    if not token or len(token) > 256:
        raise HTTPException(status_code=401, detail="Sessão inválida.")
    with database() as connection:
        cursor = connection.cursor(dictionary=True)
        try:
            cursor.execute(
                "SELECT u.id, u.name, u.email FROM app_users u JOIN app_sessions s "
                "ON s.user_id = u.id WHERE s.token_hash = %s AND s.expires_at > UTC_TIMESTAMP()",
                (token_hash(token),),
            )
            user = cursor.fetchone()
        finally:
            cursor.close()
    if not user:
        raise HTTPException(status_code=401, detail="Sessão inválida ou expirada.")
    return user


@router.post("/auth/register", status_code=status.HTTP_201_CREATED)
def register(body: RegisterRequest):
    name = body.name.strip()
    email = body.email.strip().lower()
    if not name or email.count("@") != 1 or any(c.isspace() for c in email):
        raise HTTPException(status_code=422, detail="Informe nome e e-mail válidos.")
    with database() as connection:
        cursor = connection.cursor()
        try:
            cursor.execute(
                "INSERT INTO app_users (name, email, password_hash) VALUES (%s, %s, %s)",
                (name, email, hash_password(body.password)),
            )
            connection.commit()
        except IntegrityError:
            connection.rollback()
            raise HTTPException(status_code=409, detail="E-mail já cadastrado.")
        finally:
            cursor.close()
    return {"message": "Cadastro realizado. Faça login para continuar."}


@router.post("/auth/login")
def login(body: LoginRequest):
    with database() as connection:
        cursor = connection.cursor(dictionary=True)
        try:
            cursor.execute("SELECT id, name, email, password_hash FROM app_users WHERE email = %s",
                           (body.email.strip().lower(),))
            user = cursor.fetchone()
            if not user or not verify_password(body.password, user["password_hash"]):
                raise HTTPException(status_code=401, detail="E-mail ou senha inválidos.")
            token = secrets.token_urlsafe(32)
            expires = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=12)
            cursor.execute("INSERT INTO app_sessions (token_hash, user_id, expires_at) VALUES (%s, %s, %s)",
                           (token_hash(token), user["id"], expires))
            connection.commit()
            return {"token": token, "user": {"id": user["id"], "name": user["name"], "email": user["email"]}}
        finally:
            cursor.close()


@router.get("/auth/me")
def me(user=Depends(current_user)):
    return user


@router.post("/auth/logout", status_code=204)
def logout(authorization: str = Header(), user=Depends(current_user)):
    with database() as connection:
        cursor = connection.cursor()
        try:
            cursor.execute("DELETE FROM app_sessions WHERE token_hash = %s AND user_id = %s",
                           (token_hash(authorization[7:]), user["id"]))
            connection.commit()
        finally:
            cursor.close()
    return Response(status_code=204)


@router.post("/reports", status_code=201)
def create_report(body: ReportRequest, user=Depends(current_user)):
    address = body.address.strip()
    if not address:
        raise HTTPException(status_code=422, detail="Informe o endereço.")
    try:
        image_bytes = base64.b64decode(body.image, validate=True)
        if not image_bytes or len(image_bytes) > MAX_IMAGE_BYTES:
            raise ValueError("Invalid image size")
        with Image.open(io.BytesIO(image_bytes)) as image:
            image_format = image.format
            image.verify()
        if image_format not in ("JPEG", "PNG", "WEBP"):
            raise ValueError("Invalid image format")
    except (ValueError, binascii.Error, UnidentifiedImageError, OSError, Image.DecompressionBombError):
        raise HTTPException(status_code=422, detail="Envie uma imagem JPEG, PNG ou WebP válida de até 5 MB.")
    image_type = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}[image_format]
    with database() as connection:
        cursor = connection.cursor()
        try:
            cursor.execute(
                "INSERT INTO app_reports (user_id, region, address, probability, is_demo, image_type, image_data) "
                "VALUES (%s, %s, %s, %s, TRUE, %s, %s)",
                (user["id"], body.region, address, 0.50, image_type, image_bytes),
            )
            report_id = cursor.lastrowid
            connection.commit()
        finally:
            cursor.close()
    return {"id": report_id}


@router.get("/reports")
def list_reports(user=Depends(current_user)):
    with database() as connection:
        cursor = connection.cursor(dictionary=True)
        try:
            cursor.execute(
                "SELECT id, region, address, probability, is_demo, created_at FROM app_reports "
                "WHERE user_id = %s ORDER BY created_at DESC, id DESC LIMIT 100",
                (user["id"],),
            )
            return cursor.fetchall()
        finally:
            cursor.close()


@router.get("/reports/{report_id}/image")
def report_image(report_id: int, user=Depends(current_user)):
    with database() as connection:
        cursor = connection.cursor(dictionary=True)
        try:
            cursor.execute("SELECT image_type, image_data FROM app_reports WHERE id = %s AND user_id = %s",
                           (report_id, user["id"]))
            report = cursor.fetchone()
        finally:
            cursor.close()
    if not report:
        raise HTTPException(status_code=404, detail="Relatório não encontrado.")
    return Response(content=report["image_data"], media_type=report["image_type"],
                    headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"})


@router.delete("/reports/{report_id}", status_code=204)
def delete_report(report_id: int, user=Depends(current_user)):
    with database() as connection:
        cursor = connection.cursor()
        try:
            cursor.execute("DELETE FROM app_reports WHERE id = %s AND user_id = %s", (report_id, user["id"]))
            if cursor.rowcount == 0:
                raise HTTPException(status_code=404, detail="Relatório não encontrado.")
            connection.commit()
        finally:
            cursor.close()
    return Response(status_code=204)
