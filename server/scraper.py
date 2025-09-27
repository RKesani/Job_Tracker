import re
import requests
from typing import Optional
from urllib.parse import urlparse, parse_qs
from bs4 import BeautifulSoup

# Selenium fallback
from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager


USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/127.0.0.0 Safari/537.36"
)


def normalize_text(text: str) -> str:
    text = re.sub(r"\r\n?", "\n", text)
    text = re.sub(r"\t", " ", text)
    text = re.sub(r"\u00a0", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = "\n".join(line.rstrip() for line in text.splitlines())
    return text.strip()


def clean_text_from_html(html: str) -> tuple[str, str]:
    soup = BeautifulSoup(html, "lxml")
    for tag_name in ["script", "style", "noscript", "template", "iframe"]:
        for tag in soup.find_all(tag_name):
            tag.decompose()

    title = soup.title.string.strip() if soup.title and soup.title.string else None
    text = normalize_text(soup.get_text("\n"))
    return title, text


def looks_incomplete(text: str) -> bool:
    if not text:
        return True
    if len(text) < 500:
        return True
    lowered = text.lower()
    return any(m in lowered for m in [
        "enable javascript", "your browser does not support",
        "loading...", "please wait"
    ])


def fetch_with_requests(url: str) -> tuple[str, str]:
    headers = {"User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.9"}
    resp = requests.get(url, headers=headers, timeout=20)
    resp.raise_for_status()
    return clean_text_from_html(resp.text)


def parse_ashby_job_id(url: str) -> Optional[tuple[str, str]]:
    parsed = urlparse(url)
    host = (parsed.netloc or "").lower()
    if "ashbyhq.com" not in host:
        return None

    path_parts = [p for p in (parsed.path or "").strip("/").split("/") if p]
    board_slug = path_parts[0] if path_parts else None

    qs = parse_qs(parsed.query)
    job_id = qs.get("ashby_jid", [None])[0] or qs.get("id", [None])[0]
    if not job_id:
        for part in path_parts[1:]:
            m = re.search(
                r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}",
                part,
            )
            if m:
                job_id = m.group(0)
                break

    if board_slug and job_id:
        return board_slug, job_id
    return None


def fetch_with_greenhouse_api(url: str) -> Optional[tuple[str, str]]:
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    if host not in {"boards.greenhouse.io", "boards.eu.greenhouse.io"}:
        return None

    parts = [p for p in parsed.path.strip("/").split("/") if p]
    if len(parts) < 3:
        return None

    board_token = parts[0]
    if parts[1] not in {"jobs", "job"}:
        return None
    job_id_part = parts[2]
    m = re.search(r"\d+", job_id_part)
    if not m:
        return None
    job_id = m.group(0)

    api_url = f"https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs/{job_id}"
    resp = requests.get(api_url, headers={"User-Agent": USER_AGENT}, timeout=20)
    if resp.status_code != 200:
        return None

    data = resp.json()
    title = data.get("title")
    content_html = data.get("content", "")
    _, text = clean_text_from_html(content_html)
    return title, text


def fetch_with_selenium(url: str) -> tuple[str, str]:
    options = ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument(f"--user-agent={USER_AGENT}")

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    try:
        driver.set_page_load_timeout(40)
        driver.get(url)

        WebDriverWait(driver, 20).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )

        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )

        js_text = driver.execute_script(
            "return (document.body && document.body.innerText) ? document.body.innerText : '';"
        )
        text = normalize_text(js_text)
        return driver.title, text
    finally:
        driver.quit()


