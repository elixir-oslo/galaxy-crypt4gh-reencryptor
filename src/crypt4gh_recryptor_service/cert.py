from pathlib import Path

from crypt4gh_recryptor_service.config import LOCALHOST
from crypt4gh_recryptor_service.util import run_in_subprocess


def generate_uvicorn_ssl_cert_options(settings):
    if settings.host == LOCALHOST:
        return f'--ssl-certfile {settings.localhost_certfile_path} ' \
               f'--ssl-keyfile {settings.localhost_keyfile_path} '
    else:
        return ''


def generate_keypair(private_key, public_key, passphrase, comment, verbose: bool = False):
    run_in_subprocess(
        f'crypt4gh-recryptor generate-keypair'
        f' --private {private_key}'
        f' --public {public_key}' + (f' --passphrase "{passphrase}"' if passphrase else '') +
        (f' --comment "{comment}"' if comment else ''),
        verbose=verbose)


def setup_localhost_ssl_cert(settings):
    run_in_subprocess('mkcert -install', verbose=True)
    certfile_path = settings.localhost_certfile_path
    keyfile_path = settings.localhost_keyfile_path
    if not (certfile_path.exists() and keyfile_path.exists()):
        run_in_subprocess(
            f'mkcert -cert-file {certfile_path} '
            f'-key-file {keyfile_path} '
            f'{LOCALHOST}',
            verbose=True)
    certfile_path.chmod(mode=0o600)
    keyfile_path.chmod(mode=0o600)
    return certfile_path, keyfile_path


def get_ssl_root_cert_path() -> Path:
    results = run_in_subprocess('mkcert -CAROOT', verbose=True, capture_output=True)
    path = Path(results.stdout.strip(), 'rootCA.pem')
    print(path)
    return path
