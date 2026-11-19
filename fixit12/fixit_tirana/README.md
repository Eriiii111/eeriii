# FixIt Tirana

## Nisja në Visual Studio Code

1. Hap në VS Code dosjen `fixit_tirana` (ajo që përmban `backend`, `frontend` dhe `requirements.txt`).
2. Hap `Terminal → New Terminal` dhe instalo varësitë:

   ```powershell
   python -m pip install -r requirements.txt
   ```

3. Kopjo `.env.example` si `.env`. Vendos çelësin tënd Gemini te `GEMINI_API_KEY`.
4. Krijo administratorin dhe sekretin e sesionit:

   ```powershell
   python backend/create_admin.py
   ```

   Zgjidh username dhe fjalëkalim të fortë (minimumi 12 karaktere). Ky hap shton `ADMIN_PASSWORD_HASH` dhe `SECRET_KEY` në `.env` dhe ruan konfigurimet e tjera.
5. Në VS Code zgjidh **Run and Debug → FixIt Tirana (Run Without Debugging)** dhe shtyp **Ctrl+F5**.
6. Hape `http://127.0.0.1:8000` për faqen publike ose `http://127.0.0.1:8000/login.html` për hyrjen admin.

Mos e hap `index.html` drejtpërdrejt dhe mos përdor Live Server për aplikacionin e plotë; FastAPI duhet të jetë duke punuar.

## Gemini

Gemini përdoret vetëm nga backend-i. Çelësi mbahet në `.env` dhe nuk duhet vendosur në HTML, JavaScript ose GitHub. Nëse çelësi është ekspozuar, revokoje dhe krijo një të ri në Google AI Studio. `GEMINI_MODEL` parazgjedh `gemini-2.5-flash`.

Nëse Gemini nuk përgjigjet, kontrollo se `.env` është në rrënjën e `fixit_tirana`, çelësi është i vlefshëm dhe ke internet. Ndalo e rinis serverin pasi ndryshon `.env`.

## Struktura

- `backend/main.py` — FastAPI, hyrja admin dhe endpoint-et.
- `backend/database.py` — databaza SQLite.
- `backend/ai_assistant.py` — integrimi me Google Gemini.
- `backend/create_admin.py` — krijon hash-in e fjalëkalimit të administratorit.
- `frontend/` — faqet, stilet dhe JavaScript-i.
