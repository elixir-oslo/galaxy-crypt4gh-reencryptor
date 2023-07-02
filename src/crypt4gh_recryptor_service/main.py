from pathlib import Path

from crypt4gh_recryptor_service.config import get_settings, LOCALHOST, ServerMode, setup_files
from crypt4gh_recryptor_service.util import run_in_subprocess
import typer

app = typer.Typer()


def _setup_and_run(server_mode: ServerMode):
    setup_files(server_mode)
    settings = get_settings(server_mode)

    if settings.host == LOCALHOST:
        run_in_subprocess('mkcert -install')

        certfile_path = settings.localhost_certfile_path
        keyfile_path = settings.localhost_keyfile_path

        if not (certfile_path.exists() and keyfile_path.exists()):
            run_in_subprocess(f'mkcert -cert-file {certfile_path} '
                              f'-key-file {keyfile_path} '
                              f'{LOCALHOST}')

        certfile_path.chmod(mode=0o600)
        keyfile_path.chmod(mode=0o600)

        uvicorn_ssl_options = f'--ssl-certfile {certfile_path} ' \
                              f'--ssl-keyfile {keyfile_path} '
    else:
        uvicorn_ssl_options = ''

    if server_mode == ServerMode.USER:
        for key_path in [settings.user_private_key_path, settings.user_public_key_path]:
            if not key_path.exists():
                raise ValueError(f'User key file "{key_path}" is missing!')

    run_in_subprocess(f'uvicorn --host {settings.host} --port {settings.port} '
                      f'{uvicorn_ssl_options}{"--reload " if settings.dev_mode else ""}'
                      f'--app-dir {Path(__file__).parent} {server_mode.value}:app')


@app.command()
def user():
    """Runs crypt4gh-recryptor-service in user mode"""
    _setup_and_run(ServerMode.USER)


@app.command()
def compute():
    """Runs crypt4gh-recryptor-service in compute mode"""
    _setup_and_run(ServerMode.COMPUTE)


if __name__ == '__main__':
    app()
