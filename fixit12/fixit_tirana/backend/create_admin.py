import getpass
import hashlib
import secrets
from pathlib import Path

from dotenv import load_dotenv

PROJECT_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = PROJECT_DIR / ".env"


def main():
    load_dotenv(ENV_FILE)
    username = input("Username i administratorit [admin]: ").strip() or "admin"
    password = getpass.getpass("Vendos fjalëkalim të fortë (minimumi 12 karaktere): ")
    confirm = getpass.getpass("Përsërite fjalëkalimin: ")
    if len(password) < 12:
        raise SystemExit("Fjalëkalimi duhet të ketë të paktën 12 karaktere.")
    if password != confirm:
        raise SystemExit("Fjalëkalimet nuk përputhen.")

    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), 310_000
    ).hex()
    existing = ENV_FILE.read_text(encoding="utf-8") if ENV_FILE.exists() else ""
    lines = [
        line for line in existing.splitlines()
        if not line.startswith(("ADMIN_USERNAME=", "ADMIN_PASSWORD=", "ADMIN_PASSWORD_HASH="))
    ]
    lines.extend((f"ADMIN_USERNAME={username}", f"ADMIN_PASSWORD_HASH={salt}${digest}"))
    if not any(line.startswith("SECRET_KEY=") for line in lines):
        lines.append(f"SECRET_KEY={secrets.token_urlsafe(48)}")
    ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Administratori u konfigurua. .env ruhet te: {ENV_FILE}")


if __name__ == "__main__":
    main()
