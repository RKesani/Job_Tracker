import re
import time
import json
from datetime import datetime, timezone
import requests
from urllib.parse import urlparse, parse_qs
from bs4 import BeautifulSoup
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl
from typing import Optional, List

# Selenium fallback
from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException
from webdriver_manager.chrome import ChromeDriverManager

from .extractors import (
    run_llm_extract_fields,
    derive_title_from_text,
)
from .scraper import (
    looks_incomplete,
    fetch_with_requests,
    parse_ashby_job_id,
    fetch_with_greenhouse_api,
    fetch_with_selenium,
)

class ScrapeRequest(BaseModel):
    url: HttpUrl
    use_js: Optional[bool] = None


class ScrapeResponse(BaseModel):
    url: str
    title: Optional[str]
    text: str
    job_board: Optional[str] = None
    job_id: Optional[str] = None


class ExtractRequest(BaseModel):
    url: HttpUrl
    use_js: Optional[bool] = None


class ExtractResponse(BaseModel):
    title: Optional[str] = None
    experience: Optional[str] = None
    date: Optional[str] = None
    skills: List[str] = []


def today_iso_date() -> str:
    return datetime.now(timezone.utc).date().isoformat()


# ---------- FastAPI ----------

app = FastAPI(title="Job Text Scraper", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # dev only
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/scrape", response_model=ScrapeResponse)
def scrape(req: ScrapeRequest):
    url = str(req.url)

    # Parse Ashby board/id when relevant
    board_slug: Optional[str] = None
    job_id: Optional[str] = None
    try:
        parsed_board_and_id = parse_ashby_job_id(url)
        if parsed_board_and_id:
            board_slug, job_id = parsed_board_and_id
            return ScrapeResponse(url=url, title=None, text=None, job_board=board_slug, job_id=job_id)
    except Exception:
        board_slug, job_id = None, None


    # 2. Try Greenhouse boards API
    try:
        result = fetch_with_greenhouse_api(url)
        if result:
            title, text = result
            final_title = title or derive_title_from_text(text)
            return ScrapeResponse(url=url, title=final_title, text=text, job_board=board_slug, job_id=job_id)
    except Exception:
        pass

    # 3. Try plain requests
    if not req.use_js:
        try:
            title, text = fetch_with_requests(url)
            if not looks_incomplete(text):
                final_title = title or derive_title_from_text(text)
                return ScrapeResponse(url=url, title=final_title, text=text, job_board=board_slug, job_id=job_id)
        except Exception:
            pass

    # 4. Selenium fallback
    try:
        title, text = fetch_with_selenium(url)
        final_title = title or derive_title_from_text(text)
        return ScrapeResponse(url=url, title=final_title, text=text, job_board=board_slug, job_id=job_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to scrape: {e}")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/extract", response_model=ExtractResponse)
def extract(req: ExtractRequest):
    url = str(req.url)

    # Reuse scraper pipeline to get title + text first
    # 1. Try Greenhouse API
    try:
        result = fetch_with_greenhouse_api(url)
        if result:
            title, text = result
            fields = run_llm_extract_fields(title, text)
            return ExtractResponse(
                title=fields.get("title"),
                experience=fields.get("experience"),
                date=today_iso_date(),
                skills=fields.get("skills", [])[:5],
            )
    except Exception:
        pass

    # 2. Try requests
    if not req.use_js:
        try:
            title, text = fetch_with_requests(url)
            if not looks_incomplete(text):
                print(title)
                fields = run_llm_extract_fields(title, text)
                return ExtractResponse(
                    title=fields.get("title"),
                    experience=fields.get("experience"),
                    date=today_iso_date(),
                    skills=fields.get("skills", [])[:5],
                )
        except Exception:
            pass

    # 3. Selenium fallback
    try:
        title, text = fetch_with_selenium(url)
        fields = run_llm_extract_fields(title, text)
        return ExtractResponse(
            title=fields.get("title"),
            experience=fields.get("experience"),
            date=today_iso_date(),
            skills=fields.get("skills", [])[:5],
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to extract: {e}")
