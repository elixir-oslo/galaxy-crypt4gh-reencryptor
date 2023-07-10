from base64 import b64decode, b64encode
from datetime import datetime
from hashlib import sha256
from pathlib import Path
from subprocess import CalledProcessError
import tempfile
from typing import Annotated, Tuple, Union

from crypt4gh_recryptor_service.app import app, common_info
from crypt4gh_recryptor_service.compute import GetComputeKeyInfoParams
from crypt4gh_recryptor_service.config import get_user_settings, UserSettings
from crypt4gh_recryptor_service.util import run_in_subprocess
from crypt4gh_recryptor_service.validators import to_iso
from fastapi import Depends, HTTPException, Request
from pydantic import BaseModel, Field, validator


class UserRecryptParams(BaseModel):
    crypt4gh_header: str = Field(..., min_length=1)


class UserRecryptResponse(BaseModel):
    crypt4gh_header: str = Field(..., min_length=1)
    crypt4gh_compute_keypair_id: str = Field(..., min_length=1)
    crypt4gh_compute_keypair_expiration_date: Union[datetime, str]

    _to_iso = validator('crypt4gh_compute_keypair_expiration_date', allow_reuse=True)(to_iso)


@app.get('/info')
async def info(settings: Annotated[UserSettings, Depends(get_user_settings)]) -> dict:
    return common_info(settings)


def _write_orig_header_to_file(crypt4gh_header: str, settings: UserSettings) -> Path:
    header = b64decode(crypt4gh_header)
    filename = sha256(header).hexdigest()
    path = Path(settings.headers_dir, filename)
    with open(path, 'wb') as header_file:
        header_file.write(header)
    path.chmod(mode=0o600)
    return path


def _get_temp_header_filename(settings: UserSettings) -> Path:
    return Path(tempfile.mktemp(dir=settings.headers_dir))


def _rename_temp_header(temp_header_path: Path, settings: UserSettings) -> Tuple[str, str]:
    with open(temp_header_path, 'rb') as header_file:
        header = header_file.read()
    new_filename = sha256(header).hexdigest()
    new_path = Path(settings.headers_dir, new_filename)
    temp_header_path.rename(new_path)
    new_path.chmod(mode=0o600)
    return new_filename, b64encode(header).decode('ascii')


@app.post('/recrypt_header')
async def recrypt_header(params: UserRecryptParams,
                         settings: Annotated[UserSettings, Depends(get_user_settings)],
                         request: Request) -> UserRecryptResponse:
    in_header_path = _write_orig_header_to_file(params.crypt4gh_header, settings)
    out_header_path = _get_temp_header_filename(settings)
    try:
        run_in_subprocess(
            f'crypt4gh-recryptor recrypt '
            f'--encryption-key {settings.compute_public_key_path} '
            f'-i {in_header_path} '
            f'-o {out_header_path} '
            f'--decryption-key {settings.user_private_key_path}',
            verbose=settings.dev_mode)
    except CalledProcessError as e:
        if e.returncode == 1:
            raise HTTPException(
                status_code=406,
                detail='The key header was not able to decode the header. '
                'Please make sure that the encrypted header is '
                "decryptable by the user's private key") from e
        else:
            raise e
    recrypted_header_path, header = _rename_temp_header(out_header_path, settings)

    with open(settings.compute_public_key_path, 'r') as user_private_key:
        client = request.state.client
        url = f'https://{settings.compute_host}:{settings.compute_port}/get_compute_key_info'
        payload = GetComputeKeyInfoParams(crypt4gh_user_public_key=user_private_key.read())
        response = await client.post(url, data=payload)

    key_info = response.json()

    return UserRecryptResponse(
        crypt4gh_header=header,
        crypt4gh_compute_keypair_id=key_info.get('crypt4gh_compute_keypair_id'),
        crypt4gh_compute_keypair_expiration_date=key_info.get(
            'crypt4gh_compute_keypair_expiration_date'),
    )
