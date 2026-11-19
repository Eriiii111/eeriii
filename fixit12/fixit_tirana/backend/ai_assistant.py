import asyncio
import json
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from google import genai
from google.genai import types

PROJECT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_DIR / ".env")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()

SYSTEM_PROMPT = """
Je asistenti AI i FixIt Tirana për administrimin e problemeve urbane.

Rregulla:
- Përgjigju vetëm në shqip.
- Mos shpik institucione, telefonata, statistika, afate ligjore ose veprime të kryera.
- Dalloni qartë faktet nga rekomandimet.
- Mos deklaro se institucionet kanë kryer punime.
- Jep rekomandime praktike dhe të sigurta.
- Për rreziqe urgjente, këshillo verifikim nga personeli teknik përgjegjës.
""".strip()

PRIORITIES = {"E ulët", "Mesatare", "E lartë", "Urgjente"}


def _get_client() -> genai.Client:
    # Read at call time so environment configuration is never baked into code.
    api_key = os.getenv("GEMINI_API_KEY", "").strip() or GEMINI_API_KEY
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY mungon. Shtojeni në skedarin .env të projektit."
        )
    return genai.Client(api_key=api_key)


def _extract_json(text: str) -> dict[str, Any]:
    text = (text or "").strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1].strip()
        if text.lower().startswith("json"):
            text = text[4:].strip()
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Gemini ktheu përgjigje në format të pavlefshëm.") from exc
    if not isinstance(value, dict):
        raise RuntimeError("Gemini nuk ktheu një objekt JSON.")
    return value


def _text(value: Any, default: str = "") -> str:
    return value.strip() if isinstance(value, str) and value.strip() else default


def _string_list(value: Any) -> list[str]:
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


def _generate_json(prompt: str, temperature: float) -> dict[str, Any]:
    response = _get_client().models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            temperature=temperature,
            response_mime_type="application/json",
        ),
    )
    return _extract_json(response.text or "")


async def analyze_report(report: dict) -> dict[str, Any]:
    """Kthen analizën në formatin që përdorin API-ja dhe admin.js."""
    prompt = f"""
Analizo këtë raportim urban. Kthe vetëm JSON me fushat:
- summary: përmbledhje e shkurtër
- priority: një nga E ulët, Mesatare, E lartë, Urgjente
- possible_causes: listë me shkaqe të mundshme, jo fakte të konfirmuara
- recommended_steps: listë veprimesh praktike për administratorin
- responsible_institution: shërbimi/institucioni i mundshëm; thuaj se duhet verifikuar nëse nuk dihet
- priority_reason: arsyeja e vlerësimit të prioritetit

Mos pretendo se ndonjë veprim është kryer dhe mos shpik fakte.
Raportimi:
{json.dumps(report, ensure_ascii=False)}
""".strip()
    try:
        result = await asyncio.to_thread(_generate_json, prompt, 0.2)
        priority = _text(result.get("priority"), "Mesatare")
        if priority not in PRIORITIES:
            priority = "Mesatare"
        causes = _string_list(result.get("possible_causes"))
        steps = _string_list(result.get("recommended_steps", result.get("actions")))
        institution = _text(
            result.get("responsible_institution", result.get("responsible_service")),
            "Duhet verifikuar nga shërbimi përgjegjës.",
        )
        return {
            "summary": _text(result.get("summary"), "Analiza nuk dha përmbledhje."),
            "priority": priority,
            "possible_causes": causes,
            "recommended_steps": steps,
            "responsible_institution": institution,
            "priority_reason": _text(result.get("priority_reason"), "Vlerësim orientues bazuar në përshkrimin e raportimit."),
            # Keep aliases for compatibility with the earlier AI response format.
            "responsible_service": institution,
            "actions": steps,
            "citizen_notice": _text(result.get("citizen_notice")),
        }
    except Exception as exc:
        raise RuntimeError(_friendly_error(exc)) from exc


async def suggest_solutions(category: str, location: str, description: str) -> dict[str, Any]:
    """Kthen saktësisht formatin e opsioneve që pret frontend/admin.js."""
    prompt = f"""
Përgatit saktësisht 3 alternativa të arsyeshme për raportimin urban më poshtë.
Kthe vetëm JSON me fushën options, një listë me 3 objekte. Çdo objekt ka:
- title: titull i shkurtër
- summary: shpjegim i shkurtër
- steps: listë hapash të mundshëm
- responsible_institution: institucion/shërbim i mundshëm, me shënim se duhet verifikuar
- timeframe: vlerësim i përafërt, jo premtim
- tradeoff: kufizim ose kompromis i mundshëm
Mos paraqit afatet si të garantuara dhe mos pretendo se puna është kryer.
Kategori: {category}
Vendndodhja: {location}
Përshkrimi: {description}
""".strip()
    try:
        result = await asyncio.to_thread(_generate_json, prompt, 0.25)
        raw_options = result.get("options", result.get("solutions", []))
        if not isinstance(raw_options, list):
            raw_options = []
        options = []
        for item in raw_options[:3]:
            if not isinstance(item, dict):
                continue
            options.append({
                "title": _text(item.get("title"), "Alternativë për shqyrtim"),
                "summary": _text(item.get("summary"), _text(item.get("description"))),
                "steps": _string_list(item.get("steps", item.get("actions"))),
                "responsible_institution": _text(
                    item.get("responsible_institution", item.get("responsible_service")),
                    "Duhet verifikuar nga shërbimi përgjegjës.",
                ),
                "timeframe": _text(item.get("timeframe"), "Vlerësohet pas inspektimit"),
                "tradeoff": _text(item.get("tradeoff"), "Kërkon verifikim në terren."),
            })
        while len(options) < 3:
            options.append({
                "title": f"Alternativë {len(options) + 1} për shqyrtim",
                "summary": "Duhet vlerësuar nga ekipi përgjegjës pas verifikimit në terren.",
                "steps": [],
                "responsible_institution": "Duhet verifikuar nga shërbimi përgjegjës.",
                "timeframe": "Vlerësohet pas inspektimit",
                "tradeoff": "Kërkon verifikim në terren.",
            })
        return {"options": options}
    except Exception as exc:
        raise RuntimeError(_friendly_error(exc)) from exc


async def answer_admin_question(
    question: str,
    history: list[dict],
    report: dict | None = None,
) -> str:
    conversation = []
    for message in history[-20:]:
        role = "Administratori" if message.get("role") == "user" else "Asistenti"
        content = str(message.get("content", "")).strip()
        if content:
            conversation.append(f"{role}: {content}")
    report_context = (
        "Raportimi i zgjedhur:\n" + json.dumps(report, ensure_ascii=False)
        if report else "Nuk është zgjedhur raportim."
    )
    prompt = f"""
{report_context}
Biseda e mëparshme:
{chr(10).join(conversation)}

Pyetja e administratorit:
{question}

Përgjigju vetëm me informacionin e dhënë dhe shëno qartë pasigurinë.
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
            raise RuntimeError("Gemini ktheu përgjigje bosh.")
        return answer
    except Exception as exc:
        raise RuntimeError(_friendly_error(exc)) from exc


def _friendly_error(exc: Exception) -> str:
    text = str(exc).lower()
    if any(term in text for term in ("api_key", "api key", "unauthenticated", "permission_denied")):
        return "Çelësi Gemini është i pavlefshëm ose nuk ka leje për këtë API. Kontrollo çelësin në .env."
    if any(term in text for term in ("429", "quota", "resource exhausted")):
        return "Është arritur kufiri i kërkesave Gemini. Provo përsëri më vonë."
    if "404" in text or "not found" in text:
        return "Modeli Gemini i konfiguruar nuk është i disponueshëm. Kontrollo GEMINI_MODEL në .env."
    if any(term in text for term in ("timeout", "connection", "network")):
        return "Nuk u vendos lidhja me Gemini. Kontrollo internetin dhe provo përsëri."
    return "Ndodhi gabim gjatë komunikimit me Gemini. Kontrollo konfigurimin dhe terminalin e serverit."
