from pathlib import Path
import secrets
path=Path('.env')
if path.exists():
    print('.env already exists; preserved existing configuration.')
else:
    path.write_text(Path('.env.example').read_text().replace('replace-with-a-long-random-secret',secrets.token_hex(32)))
    path.chmod(0o600)
    print('Created .env with a random signing secret. Demo mode is enabled.')
