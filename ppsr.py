import asyncio
import platform
import random
import os
import uuid
import logging
from logging.handlers import TimedRotatingFileHandler
from dotenv import load_dotenv

# 🪟 Fix Playwright subprocess issue on Windows
if platform.system() == "Windows":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from playwright.async_api import async_playwright
import uvicorn

# Load environment variables
load_dotenv()

# ------------------------
# Logging setup
# ------------------------
BASE_DIR = os.path.dirname(__file__)
LOG_DIR = os.path.join(BASE_DIR, "logs")
os.makedirs(LOG_DIR, exist_ok=True)

logger = logging.getLogger("ppsr")
logger.setLevel(logging.INFO)
if not logger.handlers:
    fh = TimedRotatingFileHandler(os.path.join(LOG_DIR, "ppsr.log"),
                                  when="midnight", backupCount=7, encoding="utf-8")
    ch = logging.StreamHandler()
    fmt = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
    fh.setFormatter(fmt); ch.setFormatter(fmt)
    logger.addHandler(fh); logger.addHandler(ch)

app = FastAPI(title="PPSR Automation API", version="1.1.0")

# Slow-down and selectors
SLOW_MO_MS = 1500  # slows every Playwright action (human-like)
WAIT_AFTER_ACTION_MS = 2400  # base waits between major steps
DECLARATION_CHECKBOX = "#ctl00_ctl00_m_cpContent_cbDeclaration_cbDeclaration"
POPUP_OK_SELECTOR = "#confirmation_bOkay"  # OK button on confirmation modal
MAIN_MENU = "#mainMenu"
VIN_INPUT = "#ctl00_ctl00_m_cpProgressWizard_ucPW_ucSN_ucSN_txtVIN"
SEARCH_DECLARATION_CB = "#ctl00_ctl00_m_cpProgressWizard_ucPW_ucSN_ucDeclarationCheckboxAndContent_cbDeclaration"
VIN_WATERMARK_FOCUS_JS = "OnWatermarkTextboxFocus('ctl00_ctl00_m_cpProgressWizard_ucPW_ucSN_ucSN_txtVIN')"
VIN_WATERMARK_BLUR_JS = "OnWatermarkTextboxBlur('ctl00_ctl00_m_cpProgressWizard_ucPW_ucSN_ucSN_txtVIN')"
SEARCH_BUTTON = "#ctl00_ctl00_m_cpProgressWizard_ucPW_btnNext"
PLATE_VALUE_ID = "#ctl00_ctl00_m_cpProgressWizard_ucPW_ucR_ucRM_ucNevdisInformationForMultiple_rptMotorVehicles_ctl00_lblPlateNumberValue"
LOGIN_BUTTON = "#ctl00_ctl00_m_cpContent_btnLogin"

# Human-like helpers
async def human_pause(min_ms: int = 900, max_ms: int = 1800):
    await asyncio.sleep(random.uniform(min_ms / 1000.0, max_ms / 1000.0))

async def type_like_human(locator, text: str, min_delay_ms: int = 120, max_delay_ms: int = 200):
    # Click, clear, and type with per-char delay
    await locator.click()
    try:
        await locator.fill("")
    except Exception:
        try:
            await locator.press("Control+A")
            await locator.press("Backspace")
        except Exception:
            pass
    for ch in text:
        await locator.type(ch, delay=random.randint(min_delay_ms, max_delay_ms))
    await human_pause(450, 900)

async def _slow_network(route):
    # Add a small delay to every request
    await asyncio.sleep(random.uniform(0.20, 0.55))
    await route.continue_()

# ------------------------
# Request body schema
# ------------------------
class LoginRequest(BaseModel):
    username: str = Field(..., example="test_user")
    password: str = Field(..., example="secret_password")
    vin_number: str = Field(..., example="JOB-12345")
    plate_number: Optional[str] = None

# ------------------------
# Main Playwright function
# ------------------------
async def open_ppsr_site(data: LoginRequest, request_id: str):
    username = data.username
    password = data.password

    # per-request run folder
    run_dir = os.path.join(LOG_DIR, request_id)
    os.makedirs(run_dir, exist_ok=True)
    logger.info(f"[{request_id}] Start run | user={username} | vin={data.vin_number}")
    logger.info(f"[{request_id}] Logs dir: {run_dir}")
    headless_mode = str(os.getenv("HEADLESS", "true")).strip().lower() in ("1", "true", "yes", "on")
    logger.info(f"[{request_id}] Headless mode: {headless_mode}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=headless_mode,
            slow_mo=SLOW_MO_MS,  # slow down actions
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-first-run",
                "--no-default-browser-check",
            ],
        )

        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/91.0.4472.124 Safari/537.36"
            ),
        )
        # Slightly throttle network to mimic human usage
        await context.route("**/*", _slow_network)
        # Start Playwright tracing
        await context.tracing.start(screenshots=True, snapshots=True, sources=True)

        page = await context.new_page()
        # Safety: accept native JS dialogs if they appear
        async def _on_dialog(dialog):
            logger.warning(f"[{request_id}] dialog: {dialog.type} -> {dialog.message}")
            await dialog.accept()
        page.on("dialog", _on_dialog)
        # Capture console logs and request failures
        page.on("console", lambda msg: logger.info(f"[{request_id}] console.{msg.type}: {msg.text}"))
        page.on("pageerror", lambda err: logger.error(f"[{request_id}] pageerror: {err}"))
        page.on("requestfailed", lambda req: logger.warning(f"[{request_id}] requestfailed: {req.method} {req.url} -> {req.failure}"))

        url = "https://transact.ppsr.gov.au/ppsr/Login"
        logger.info(f"[{request_id}] 🌐 Opening: {url}")

        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=10000)
            logger.info(f"[{request_id}] ✅ Page loaded successfully")
        except Exception as e:
            await browser.close()
            raise Exception(f"Failed to load page: {e}")

        await page.screenshot(path=os.path.join(run_dir, "ppsr_initial.png"))
        await human_pause(1200, 2200)

        # Wait for form
        try:
            await page.wait_for_selector("input[type='text'], input[type='password']", timeout=10000)
            logger.info(f"[{request_id}] ✅ Login form detected")
        except Exception:
            await page.screenshot(path=os.path.join(run_dir, "ppsr_form_not_found.png"))
            await browser.close()
            raise Exception("Login form not found")

        # Fill username (human-like typing)
        username_field = page.locator("input[type='text']").first
        if await username_field.count() > 0:
            await type_like_human(username_field, username, 130, 210)
        else:
            await browser.close()
            raise Exception("Username field not found")

        await human_pause(1200, 2400)

        # Fill password (human-like typing)
        password_field = page.locator("input[type='password']").first
        if await password_field.count() > 0:
            await type_like_human(password_field, password, 130, 210)
        else:
            await browser.close()
            raise Exception("Password field not found")

        await human_pause(1200, 2400)

        # Tick declaration checkbox (make it true)
        try:
            await page.wait_for_selector(DECLARATION_CHECKBOX, timeout=10000)
            if not await page.is_checked(DECLARATION_CHECKBOX):
                await page.check(DECLARATION_CHECKBOX)
                logger.info(f"[{request_id}] ☑️  Declaration checkbox checked")
            else:
                logger.info(f"[{request_id}] ☑️  Declaration checkbox already checked")
        except Exception as e:
            await page.screenshot(path=os.path.join(run_dir, "ppsr_checkbox_error.png"))
            await browser.close()
            raise Exception(f"Declaration checkbox not found or not clickable: {e}")

        await human_pause(1400, 2600)

        logger.info(f"[{request_id}] 🔐 Credentials entered for: {username}")

        # Click login (prefer explicit login button, fallback to generic submit/Enter)
        try:
            # prefer explicit ID button
            await page.wait_for_selector(LOGIN_BUTTON, timeout=10000)
            login_btn = page.locator(LOGIN_BUTTON).first
            await login_btn.scroll_into_view_if_needed()
            try:
                # Click and wait for navigation/network idle if it occurs
                await asyncio.gather(
                    page.wait_for_load_state("networkidle", timeout=30000),
                    login_btn.click()
                )
            except Exception:
                # fallback if no navigation happens
                await login_btn.click(force=True)
                await human_pause(1600, 2600)
            logger.info(f"[{request_id}] 🔐 Login button clicked (explicit)")
        except Exception as e:
            logger.warning(f"[{request_id}] ⚠️ Explicit login button not available: {e}. Falling back...")
            try:
                # fallback: generic submit or Enter
                generic = await page.query_selector("input[type='submit'], button[type='submit']")
                if generic:
                    await generic.click()
                    logger.info(f"[{request_id}] 🔐 Login button clicked (generic)")
                else:
                    await page.keyboard.press("Enter")
                    logger.info(f"[{request_id}] 🔐 Pressed Enter to submit")
            except Exception as ex:
                logger.error(f"[{request_id}] ⚠️ Login fallback failed: {ex}")

        # Give time for modal/navigation to appear
        await human_pause(1600, 2600)

        # -------------------------------
        # Navigate: hover PPSR Search -> click first submenu
        # -------------------------------
        try:
            await page.wait_for_selector(MAIN_MENU, timeout=10000)
            menu_root = page.locator(MAIN_MENU)

            ppsr_search = menu_root.locator("a:has-text('PPSR Search')").first
            await ppsr_search.scroll_into_view_if_needed()
            await ppsr_search.hover()
            logger.info(f"[{request_id}] 🖱️ Hovered 'PPSR Search'")
            await human_pause(900, 1600)

            first_level_menu = menu_root.locator("li:has(> a:has-text('PPSR Search')) > ul.childmenu").first
            await first_level_menu.wait_for(state="visible", timeout=10000)

            search_by_serial = first_level_menu.locator("a:has-text('Search by serial number')").first
            await search_by_serial.hover()
            logger.info(f"[{request_id}] 🖱️ Hovered 'Search by serial number'")
            await human_pause(900, 1600)

            second_level_menu = search_by_serial.locator("xpath=..").locator("ul.childmenu").first
            if await second_level_menu.count() == 0:
                second_level_menu = menu_root.locator("li:has(> a:has-text('Search by serial number')) > ul.childmenu").first
            await second_level_menu.wait_for(state="visible", timeout=10000)

            first_item = second_level_menu.locator("li a").first
            first_item_text = await first_item.inner_text()
            await first_item.click()
            logger.info(f"[{request_id}] ✅ Clicked first submenu item: {first_item_text.strip()}")

            await page.wait_for_load_state("networkidle")
            await human_pause(1200, 2200)
            logger.info(f"[{request_id}] 🔗 Landed on: {page.url}")
            await page.screenshot(path=os.path.join(run_dir, "ppsr_after_menu_nav.png"))
        except Exception as e:
            logger.error(f"[{request_id}] ⚠️ Menu navigation failed: {e}")
            await page.screenshot(path=os.path.join(run_dir, "ppsr_nav_error.png"))

        # Fill VIN and tick declaration on the search page
        try:
            await page.wait_for_selector(VIN_INPUT, timeout=10000)
            vin_input = page.locator(VIN_INPUT)
            await vin_input.scroll_into_view_if_needed()
            try:
                await page.evaluate(VIN_WATERMARK_FOCUS_JS)
            except Exception:
                pass
            await vin_input.click()
            try:
                await vin_input.fill("")
            except Exception:
                await vin_input.press("Control+A")
                await vin_input.press("Backspace")
            # Slow, human-like typing for VIN
            await type_like_human(vin_input, data.vin_number, 140, 220)
            try:
                await page.evaluate(VIN_WATERMARK_BLUR_JS)
            except Exception:
                pass
            await human_pause(900, 1500)
            logger.info(f"[{request_id}] 🔎 Entered VIN: {data.vin_number[:6]}********")

            await page.wait_for_selector(SEARCH_DECLARATION_CB, timeout=5000)
            if not await page.is_checked(SEARCH_DECLARATION_CB):
                await page.check(SEARCH_DECLARATION_CB)
                logger.info(f"[{request_id}] ☑️  Search declaration checkbox checked")
            else:
                logger.info(f"[{request_id}] ☑️  Search declaration checkbox already checked")

            await human_pause(1100, 1900)
            await page.screenshot(path=os.path.join(run_dir, "ppsr_after_vin_and_decl.png"))
        except Exception as e:
            logger.error(f"[{request_id}] ⚠️ VIN/Declaration step failed: {e}")
            await page.screenshot(path=os.path.join(run_dir, "ppsr_vin_decl_error.png"))

        # Click the "Search" button
        try:
            await page.wait_for_selector(SEARCH_BUTTON, timeout=5000)
            search_btn = page.locator(SEARCH_BUTTON)
            await search_btn.scroll_into_view_if_needed()
            try:
                await asyncio.gather(
                    page.wait_for_load_state("networkidle", timeout=10000),
                    search_btn.click()
                )
            except Exception:
                await search_btn.click()
                await human_pause(1600, 2600)
            logger.info(f"[{request_id}] 🔍 Clicked Search")
            await human_pause(1300, 2200)
            await page.screenshot(path=os.path.join(run_dir, "ppsr_after_search_click.png"))
        except Exception as e:
            logger.error(f"[{request_id}] ⚠️ Search button click failed: {e}")
            await page.screenshot(path=os.path.join(run_dir, "ppsr_search_click_error.png"))

        # Extract Registration plate number from results
        try:
            # Small settle wait
            await human_pause(1300, 2100)
            plate_loc = page.locator(PLATE_VALUE_ID)
            if await plate_loc.count() > 0:
                await plate_loc.first.wait_for(state="visible", timeout=10000)
                plate_number = (await plate_loc.first.inner_text()).strip()
            else:
                dt_label = page.locator("dt:has-text('Registration plate number:')").first
                await dt_label.wait_for(state="visible", timeout=10000)
                dd_value = dt_label.locator("xpath=following-sibling::dd[1]")
                plate_number = (await dd_value.inner_text()).strip()
            logger.info(f"[{request_id}] 📛 Registration plate number: {plate_number}")
            await page.screenshot(path=os.path.join(run_dir, "ppsr_plate_extracted.png"))
        except Exception as e:
            logger.error(f"[{request_id}] ⚠️ Could not extract plate number: {e}")
            await page.screenshot(path=os.path.join(run_dir, "ppsr_plate_extract_error.png"))

        await human_pause(1800, 3000)
        await page.screenshot(path=os.path.join(run_dir, "ppsr_after_login.png"))
        # Save Playwright trace
        trace_path = os.path.join(run_dir, f"trace-{request_id}.zip")
        await context.tracing.stop(path=trace_path)

        logger.info(f"[{request_id}] ✅ Browser closed after run")
        await browser.close()

        return {
            "status": "success",
            "message": "Login attempt completed",
            "plateNumber": plate_number if plate_number else None,
            "requestId": request_id,
            "logsDir": run_dir,
            "trace": trace_path,
        }

# ------------------------
# FastAPI endpoint (POST)
# ------------------------
@app.post("/open_ppsr")
async def open_ppsr(request: LoginRequest):
    """
    Example:
    POST http://127.0.0.1:8000/open_ppsr
    Body:
    {
        "username": "test_user",
        "password": "secret",
        "vin_number": "1HGCM82633A123456",
        "notes": "Initial test run"
    }
    """
    try:
        request_id = uuid.uuid4().hex[:8]
        logger.info(f"[{request_id}] HTTP /open_ppsr received")
        result = await open_ppsr_site(request, request_id)
        logger.info(f"[{request_id}] HTTP /open_ppsr completed")
        return result
    except Exception as e:
        logger.exception(f"[{request_id}] ❌ Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Health check endpoint
@app.get("/")
async def root():
    return {"message": "PPSR Automation API is running"}

# ------------------------
# Run server
# ------------------------
if __name__ == "__main__":
    uvicorn.run("ppsr:app", host="0.0.0.0", port=8000, reload=True)
