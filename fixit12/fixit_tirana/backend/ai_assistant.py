
from pathlib import Path
import asyncio
import json
import os
from typing import Any

from dotenv import load_dotenv
from google import genai
from google.genai import types


load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()

SYSTEM_PROMPT = """
Je asistenti AI i FixIt Tirana për administrimin e problemeve urbane.

Rregulla:
- Përgjigju vetëm në shqip.
- Mos shpik institucione, telefonata, statistika, afate ligjore ose veprime të kryera.
- Dalloni qartë faktet nga rekomandimet.
- Mos deklaroni se institucionet kanë kryer punime.
- Jepni rekomandime praktike dhe të sigurta.
- Për punime urgjente, theksoni nevojën për verifikim nga personeli teknik i zyrës përgjegjëse.
""".strip()


def _get_client() -> genai.Client:
    if not GEMINI_API_KEY:
        raise RuntimeError(
            "GEMINI_API_KEY mungon. Shtojeni në .env në rrënjë të projektit."
        )
    return genai.Client(api_key=GEMINI_API_KEY)


def _extract_json(text: str) -> dict[str, Any]:
    text = (text or "").strip()

    if text.startswith("```"):
        parts = text.split("```")
        if len(parts) >= 2:
            text = parts[1]
            if text.startswith("json"):
                text = text[4:]
        text = text.strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Përgjigjja e Gemini nuk ishte JSON i vlefshëm.") from exc

    if not isinstance(data, dict):
        raise RuntimeError("Përgjigjja e Gemini nuk ishte një objekt JSON.")

    return data


async def analyze_report(report: dict) -> dict:
    """Analizon raportin nga main.py dhe kthen {'summary', 'priority', ...}."""

    prompt = f"""
Analizo raportin urban dhe kthe vetëm një objekt JSON të vlefshëm.

Kërkohet të kesh këto fusha:
- summary: përmbledhje e shkurtër në shqip
- priority: E ulët, Mesatare, E lartë ose Urgjente
- responsible_service: shërbimi apo drejtoria e mundshme për shqyrtim
- actions: array me veprime praktike për administratorin
- citizen_notice: mesazh i shkurtër dhe neutral për qytetin

Mos deklaro se puna është bërë. Mos shto informacione që nuk janë dhënë në raport.

Raporti:
{json.dumps(report, ensure_ascii=False)}
""".strip()

    try:
        response = await asyncio.to_thread(
            _get_client().models.generate_content,
            model=GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                temperature=0.2,
                response_mime_type="application/json",
            ),
        )

        result = _extract_json(response.text)
        result.setdefault("summary", "")
        result.setdefault("priority", "Mesatare")
        result.setdefault("responsible_service", "")
        result.setdefault("actions", [])
        result.setdefault("citizen_notice", "")

        if result["priority"] not in {
            "E ulët",
            "Mesatare",
            "E lartë",
            "Urgjente",
        }:
            result["priority"] = "Mesatare"

        if not isinstance(result["actions"], list):
            result["actions"] = [str(result["actions"])]

        return result

    except Exception as exc:
        raise RuntimeError(_friendly_error(exc)) from exc


async def suggest_solutions(
    category: str,
    location: str,
    description: str,
) -> dict:
    """Kthehet nga POST /api/ai/suggest-solutions."""

    prompt = f"""
Jep rekomandime të arsyeshme për këtë raportim urban.

Kategori: {category}
Vendndodhja: {location}
Përshkrimi: {description}

Kthe vetëm JSON me këto fusha:
- title: titull i shkurtër
- priority: E ulët, Mesatare, E lartë ose Urgjente
- summary: përmbledhje
- solutions: array me rekomandime konkrete
- verification: çfarë duhet verifikuar para ndërhyrjes

Mos dhëno procedura ligjore ose të dhëna institucionale që nuk janë të sigurt.
""".strip()

    try:
        response = await asyncio.to_thread(
            _get_client().models.generate_content,
            model=GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                temperature=0.25,
                response_mime_type="application/json",
            ),
        )

        result = _extract_json(response.text)
        result.setdefault("title", "Rekomandime")
        result.setdefault("priority", "Mesatare")
        result.setdefault("summary", "")
        result.setdefault("solutions", [])
        result.setdefault("verification", "")

        if not isinstance(result["solutions"], list):
            result["solutions"] = [str(result["solutions"])]

        return result

    except Exception as exc:
        raise RuntimeError(_friendly_error(exc)) from exc


async def answer_admin_question(
    question: str,
    history: list[dict],
    report: dict | None = None,
) -> str:
    """Përgjigjet për chatbot-in e administratorit."""

    conversation = []
    for message in history[-20:]:
        role = "Administrator" if message.get("role") == "user" else "Asistenti"
        content = str(message.get("content", "")).strip()
        if content:
            conversation.append(f"{role}: {content}")

    report_context = ""
    if report:
        report_context = (
            "\nRaporti i zgjedhur:\n"
            + json.dumps(report, ensure_ascii=False)
            + "\n"
        )

    prompt = f"""
{report_context}
Biseda e mëparshme:
{chr(10).join(conversation)}

Pyetja e re nga administratorit:
{question}

Përgjigju vetëm duke përdorur informacionin e disponueshëm.
""".strip()

    try:
        response = await asyncio.to_thread(
            _get_client().models.generate_content,
            model=GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                temperature=0.35,
            ),
        )

        answer = (response.text or "").strip()
        if not answer:
            raise RuntimeError("Gemini ktheu një përgjigje bosh.")

        return answer

    except Exception as exc:
        raise RuntimeError(_friendly_error(exc)) from exc


def _friendly_error(exc: Exception) -> str:
    text = str(exc).lower()

    if "api_key" in text or "unauthenticated" in text:
        return "Çelësi Gemini është i pavlefshëm ose mungon."
    if "429" in text or "quota" in text or "resource exhausted" in text:
        return "Kufiri i kërkesave Gemini është arritur. Provoni përsëri më vonë."
    if "404" in text or "not found" in text:
        return "Modeli i konfiguruar Gemini nuk është i disponueshëm."
    if "timeout" in text or "connection" in text:
        return "Nuk u vendos lidhja me Gemini."

    return "Ndodhi një gabim gjatë komunikimit me Gemini."