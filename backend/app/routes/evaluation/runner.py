import asyncio
import base64
import logging
from typing import Dict, Any, Optional, Tuple, List

logger = logging.getLogger(__name__)


async def run_preview(
    files: Dict[str, Any],
    desktop_width: int = 1280,
    desktop_height: int = 720,
    mobile_width: int = 375,
    mobile_height: int = 667,
) -> Dict[str, Any]:
    from playwright.async_api import async_playwright
    from app.routes.evaluation.builder import build_preview_html

    html = build_preview_html(files)

    result = {
        "screenshot": None,
        "screenshot_mobile": None,
        "console_errors": [],
        "console_logs": [],
        "runtime_error": None,
        "rendered": False,
    }

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-setuid-sandbox"],
            )

            context = await browser.new_context(
                viewport={"width": desktop_width, "height": desktop_height},
                device_scale_factor=1,
            )
            page = await context.new_page()

            console_errors: List[str] = []

            def on_console(msg):
                if msg.type == "error":
                    console_errors.append(msg.text)

            page.on("console", on_console)
            page.on("pageerror", lambda err: console_errors.append(str(err)))

            await page.set_content(html, wait_until="networkidle", timeout=15000)

            await page.wait_for_timeout(2000)

            error_overlay_visible = await page.evaluate(
                """() => {
                    const el = document.getElementById('__error-overlay');
                    return el ? el.classList.contains('show') : false;
                }"""
            )

            if error_overlay_visible:
                result["runtime_error"] = await page.evaluate(
                    """() => document.getElementById('__error-overlay').textContent"""
                )
            else:
                result["rendered"] = True

            runtime_err = await page.evaluate(
                "() => window.__runtimeError__ || null"
            )
            if runtime_err:
                result["runtime_error"] = runtime_err

            console_logs = await page.evaluate(
                "() => window.__consoleLogs__ || []"
            )
            result["console_logs"] = console_logs
            result["console_errors"] = [l["message"] for l in console_logs if l["level"] == "error"]

            if not result["runtime_error"]:
                screenshot_bytes = await page.screenshot(
                    full_page=False, type="png"
                )
                result["screenshot"] = base64.b64encode(screenshot_bytes).decode("utf-8")

            mobile_context = await browser.new_context(
                viewport={"width": mobile_width, "height": mobile_height},
                device_scale_factor=2,
            )
            mobile_page = await mobile_context.new_page()
            await mobile_page.set_content(html, wait_until="networkidle", timeout=15000)
            await mobile_page.wait_for_timeout(1500)

            if not await mobile_page.evaluate(
                "() => document.getElementById('__error-overlay')?.classList.contains('show')"
            ):
                mobile_screenshot = await mobile_page.screenshot(
                    full_page=False, type="png"
                )
                result["screenshot_mobile"] = base64.b64encode(
                    mobile_screenshot
                ).decode("utf-8")

            await mobile_context.close()
            await context.close()
            await browser.close()

    except ImportError:
        logger.error("Playwright not installed. Run: pip install playwright && playwright install chromium")
        result["runtime_error"] = "Playwright not installed on server"
    except Exception as e:
        logger.error(f"Playwright runner error: {e}", exc_info=True)
        result["runtime_error"] = str(e)

    return result
