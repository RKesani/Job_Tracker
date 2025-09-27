import json
from typing import Optional, List, Dict, Any


# Optional MLX LLM
try:
    from mlx_lm import load as mlx_load, generate as mlx_generate
except Exception:  # pragma: no cover
    mlx_load = None
    mlx_generate = None


_LLM_MODEL = None
_LLM_TOKENIZER = None


def ensure_llm_loaded() -> bool:
    global _LLM_MODEL, _LLM_TOKENIZER
    if _LLM_MODEL is not None and _LLM_TOKENIZER is not None:
        return True
    if mlx_load is None or mlx_generate is None:
        return False
    _LLM_MODEL, _LLM_TOKENIZER = mlx_load("mlx-community/gemma-3-270m-it-8bit")
    return True


def parse_json_safely(text: str) -> Optional[Dict[str, Any]]:
    try:
        return json.loads(text)
    except Exception:
        pass
    try:
        start = text.index("{")
        end = text.rindex("}") + 1
        return json.loads(text[start:end])
    except Exception:
        return None



def derive_title_from_text(page_text: str) -> Optional[str]:
    """Use the first 50 non-empty lines and ask the LLM for the title."""
    if not page_text:
        return None
    print("Title from text")

    lines = [ln.strip() for ln in page_text.splitlines() if ln and ln.strip()]
    if not lines:
        return None

    first_lines = "\n".join(lines[:50])

    # Try LLM-based extraction first
    if ensure_llm_loaded():
        system_prompt = (
            "Given the first lines of a job posting, extract only the clean job title. "
            "Return STRICT JSON with a single key: title. No extra text."
        )
        user_prompt = (
            f"First lines (up to 50):\n{first_lines}\n\n"
            "Return JSON exactly like: {\"title\": \"Senior Software Engineer\"}"
        )

        prompt = system_prompt + "\n\n" + user_prompt
        full_prompt = prompt
        if globals().get("_LLM_TOKENIZER") is not None and getattr(_LLM_TOKENIZER, "chat_template", None) is not None:
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]
            full_prompt = _LLM_TOKENIZER.apply_chat_template(messages, add_generation_prompt=True)

        try:
            output = mlx_generate(_LLM_MODEL, _LLM_TOKENIZER, prompt=full_prompt, verbose=False)
            parsed = parse_json_safely(output)
            if isinstance(parsed, dict):
                candidate = parsed.get("title") if isinstance(parsed.get("title"), str) else None
                if candidate:
                    return candidate.strip()
        except Exception:
            pass

    return None



def run_llm_extract_fields(raw_title: Optional[str], page_text: str) -> Dict[str, Any]:
    """Return dict with keys: title, experience, skills. Date is intentionally excluded."""
    if not ensure_llm_loaded():
        return {"title": None, "experience": None, "skills": []}

    system_prompt = (
        "You extract structured fields from job postings. "
        "Return STRICT JSON only with keys: title, experience, skills. "
        "- title: Clean job title only (no company or location). "
        "- experience: Short phrase like '3+ years' or 'senior-level'. "
        "- skills: Up to 5 core skills as a JSON array of strings (concise, lowercase). "
        "If a field is missing, set it to null (or empty array for skills)."
    )
    user_prompt = (
        f"Known page title (may contain company/location):\n{raw_title or ''}\n\n"
        f"Full page text:\n{page_text}"
    )

    prompt = system_prompt + "\n\n" + user_prompt
    full_prompt = prompt
    if globals().get("_LLM_TOKENIZER") is not None and getattr(_LLM_TOKENIZER, "chat_template", None) is not None:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        full_prompt = _LLM_TOKENIZER.apply_chat_template(messages, add_generation_prompt=True)

    output = mlx_generate(_LLM_MODEL, _LLM_TOKENIZER, prompt=full_prompt, verbose=False)
    parsed = parse_json_safely(output)

    title = None
    experience = None
    skills: List[str] = []
    if isinstance(parsed, dict):
        title = parsed.get("title") if isinstance(parsed.get("title"), str) else None
        experience = parsed.get("experience") if isinstance(parsed.get("experience"), str) else None
        skills_val = parsed.get("skills")
        if isinstance(skills_val, list):
            skills = [s for s in skills_val if isinstance(s, str)]
            skills = [s.strip().lower() for s in skills][:5]

    # If title still missing, ask LLM again but focused on the first lines
    title = title or derive_title_from_text(page_text)
    return {"title": title, "experience": experience, "skills": skills}


