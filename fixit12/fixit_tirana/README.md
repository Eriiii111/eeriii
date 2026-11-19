# FixIt Tirana

## Hapja e projektit në Visual Studio Code (mënyra e rekomanduar)

1. Shkarko dhe **ekstrakto ZIP-in**.
2. Në VS Code zgjidh **File → Open Folder** dhe hap dosjen `fixit_tirana` (atë që përmban `backend`, `frontend` dhe `requirements.txt`).
3. Hap **Terminal → New Terminal**. Sigurohu që terminali ndodhet brenda dosjes `fixit_tirana`.
4. Instalo varësitë:

   ```powershell
   python -m pip install -r requirements.txt
   ```

   Nëse `python` nuk njihet në kompjuterin tënd, përdor rrugën e plotë të Python 3.12:

   ```powershell
   & "$env:LocalAppData\Programs\Python\Python312\python.exe" -m pip install -r requirements.txt
   ```

5. Krijo skedarin `.env` duke kopjuar `.env.example`. Plotëso `GEMINI_API_KEY` me çelësin tënd Gemini dhe ndrysho `ADMIN_USERNAME`, `ADMIN_PASSWORD` dhe `SECRET_KEY`.
6. Nise serverin nga terminali i VS Code:

   ```powershell
   python -m uvicorn backend.main:app --reload
   ```

   Nëse duhet, zëvendëso `python` me rrugën e plotë të Python-it si më sipër, pastaj shto `-m uvicorn backend.main:app --reload`.
7. Hape në Chrome: **http://127.0.0.1:8000**

**E rëndësishme:** mos hap `index.html` me dy klikime dhe mos përdor butonin **Go Live** për përdorimin e plotë. Live Server shërben vetëm skedarët statikë; formulari, identifikimi, databaza dhe Gemini kërkojnë FastAPI. Me komandën `uvicorn` më sipër, dizajni dhe funksionet ngarkohen nga i njëjti server.

## Konfigurimi i Gemini

Në `.env` vendos:

```env
GEMINI_API_KEY=vendos_celesin_tend
GEMINI_MODEL=gemini-2.5-flash
ADMIN_USERNAME=admin
ADMIN_PASSWORD=ndrysho-kete-fjalekalim
SECRET_KEY=vendos_nje_vlere_te_gjate_rastesisore
```

Mos e publiko `.env` dhe mos e vendos çelësin në HTML/JavaScript. Ndrysho fjalëkalimin e administratorit para përdorimit.

## Struktura

- `backend/main.py` – aplikacioni FastAPI dhe endpoint-et.
- `backend/database.py` – databaza SQLite.
- `backend/ai_assistant.py` – integrimi me Google Gemini përmes SDK-së zyrtare `google-genai`.
- `frontend/index.html` – raportimi publik.
- `frontend/login.html` – hyrja e administratorit.
- `frontend/admin.html` – paneli i administratorit.
- `frontend/styles.css` – dizajni i faqes.
- `uploads/` – fotografitë e raportimeve.

Gemini kërkon një API key të vlefshëm dhe lidhje interneti. Pa to, pjesa e AI-së do të kthejë mesazh gabimi; pjesët e tjera të faqes mund të përdoren lokalisht.
