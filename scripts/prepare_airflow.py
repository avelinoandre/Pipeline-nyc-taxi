import json
import os
from pathlib import Path
import secrets
import shlex

from cryptography.fernet import Fernet


home = Path(os.environ["AIRFLOW_HOME"])
home.mkdir(mode=0o700, parents=True, exist_ok=True)
home.chmod(0o700)
settings = home / "runtime.env"
if not settings.exists():
    values = {
        "AIRFLOW__API_AUTH__JWT_SECRET": secrets.token_urlsafe(48),
        "AIRFLOW__CORE__FERNET_KEY": Fernet.generate_key().decode(),
    }
    settings.write_text("".join(f"export {name}={shlex.quote(value)}\n" for name, value in values.items()))
    settings.chmod(0o600)
password_file = home / "ui_passwords.json"
if not password_file.exists():
    password_file.write_text(json.dumps({"andre": secrets.token_urlsafe(24)}))
    password_file.chmod(0o600)
