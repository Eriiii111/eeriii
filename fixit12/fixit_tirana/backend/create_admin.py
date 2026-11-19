import getpass, hashlib, os, secrets
from pathlib import Path

def main():
    username = input("Username i administratorit [admin]: ").strip() or "admin"
    password = getpass.getpass("Vendos fjalëkalim të fortë: ")
    confirm = getpass.getpass("Përsërite fjalëkalimin: ")
    if len(password) < 12:
        raise SystemExit("Fjalëkalimi duhet të ketë të paktën 12 karaktere.")
    if password != confirm:
        raise SystemExit("Fjalëkalimet nuk përputhen.")
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256",password.encode(),salt.encode(),310000).hex()
    env = Path(".env")
    content = env.read_text(encoding="utf-8") if env.exists() else ""
    lines = [x for x in content.splitlines() if not x.startswith(("ADMIN_USERNAME=","ADMIN_PASSWORD_HASH="))]
    lines += [f"ADMIN_USERNAME={username}",f"ADMIN_PASSWORD_HASH={salt}${digest}"]
    env.write_text("\n".join(lines)+"\n",encoding="utf-8")
    print("Administratori u konfigurua në .env.")

if __name__ == "__main__":
    main()
