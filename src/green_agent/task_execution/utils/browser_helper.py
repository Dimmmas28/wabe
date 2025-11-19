from playwright.async_api._generated import Playwright as AsyncPlaywright

from playwright.async_api import Browser
from playwright._impl._api_structures import (
    ViewportSize,
)


async def normal_launch_async(playwright: AsyncPlaywright, headless=False, args=None):
    browser = await playwright.chromium.launch(
        headless=headless,
        args=args,
        traces_dir=None,
    )
    return browser


async def normal_new_context_async(
    browser: Browser,
    storage_state=None,
    har_path=None,
    video_path=None,
    tracing=False,
    trace_screenshots=False,
    trace_snapshots=False,
    trace_sources=False,
    locale=None,
    geolocation=None,
    user_agent: str = "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36",  # "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    viewport: ViewportSize = {"width": 1280, "height": 720},
):
    context = await browser.new_context(
        storage_state=storage_state,
        user_agent=user_agent,
        viewport=viewport,
        locale=locale,
        record_har_path=har_path,
        record_video_dir=video_path,
        geolocation=geolocation,
    )

    if tracing:
        await context.tracing.start(
            screenshots=trace_screenshots,
            snapshots=trace_snapshots,
            sources=trace_sources,
        )
    return context
