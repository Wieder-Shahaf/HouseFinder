"""Shared Bright Data Web Unlocker proxy configuration.

Any scraper using Playwright can call get_proxy_launch_args() to get
the proxy kwarg dict for browser.launch() or launch_persistent_context().

When BRIGHT_DATA_HOST/USER/PASS env vars are unset, returns empty dict
(no proxy — graceful degradation).

IMPORTANT: Target URLs passed to page.goto() MUST use http:// (not https://)
when the proxy is active. The Web Unlocker handles SSL termination itself.
"""

from app.config import settings


def get_proxy_launch_args() -> dict:
    """Return Playwright-compatible proxy kwargs for browser launch.

    Returns {"proxy": {"server": ..., "username": ..., "password": ...}}
    when all three Bright Data env vars are configured.
    Returns {} when any env var is missing (proxy disabled).

    Usage:
        browser = await p.chromium.launch(**get_proxy_launch_args())
        # or
        context = await p.chromium.launch_persistent_context(
            user_data_dir, **get_proxy_launch_args()
        )
    """
    host = settings.bright_data_host
    user = settings.bright_data_user
    password = settings.bright_data_pass

    if not all([host, user, password]):
        return {}

    return {
        "proxy": {
            "server": host,
            "username": user,
            "password": password,
        }
    }


def is_proxy_enabled() -> bool:
    """Check if Bright Data proxy is fully configured."""
    return bool(
        settings.bright_data_host
        and settings.bright_data_user
        and settings.bright_data_pass
    )
