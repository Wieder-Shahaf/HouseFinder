from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )

    database_url: str = "sqlite+aiosqlite:////data/listings.db"
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_whatsapp_from: str = ""
    llm_api_key: str = ""
    app_url: str = "http://localhost:8000"

    # LLM verification settings (Phase 2)
    llm_confidence_threshold: float = 0.7
    llm_model: str = "claude-haiku-4-5"

    # Yad2 scraper settings (Phase 2) — endpoint hypothesis, confirmed in Task 3 DevTools checkpoint
    yad2_api_base_url: str = "https://gw.yad2.co.il/feed/realestate/rent"
    yad2_price_max: int = 4500
    yad2_city_code: str = "4000"
    yad2_neighborhoods: list[str] = ["כרמל", "מרכז העיר", "נווה שאנן"]
    # Confirmed via DevTools (2026-04-02): neighborhood=609 maps to כרמל
    # מרכז העיר and נווה שאנן IDs not captured — use post-scrape address.neighborhood.text filter
    yad2_neighborhood_id_carmel: int = 609

    # Madlan scraper settings (Phase 6)
    madlan_base_url: str = "https://www.madlan.co.il/rent/haifa"
    # Max pages to fetch from /api3 GraphQL (50 results/page; ~4-8 Haifa results/page)
    # 10 pages = 500 Israel-wide results = ~40-80 Haifa results covering 48h of listings
    madlan_graphql_max_pages: int = 10

    # Scheduler settings (Phase 3) — SCHED-01
    scrape_interval_hours: int = 2

    # Bright Data Web Unlocker proxy (optional — enables CAPTCHA bypass)
    bright_data_host: str = ""   # e.g. "brd.superproxy.io:33335"
    bright_data_user: str = ""   # e.g. "brd-customer-xxx-zone-web_unlocker1"
    bright_data_pass: str = ""

    # Web Push (VAPID) settings (Phase 7)
    vapid_public_key: str = ""
    vapid_private_key: str = ""
    vapid_contact_email: str = "admin@localhost"

    # Facebook scraper settings (Phase 8)
    facebook_session_path: str = "/data/facebook_session.json"


settings = Settings()
