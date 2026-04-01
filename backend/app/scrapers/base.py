from dataclasses import dataclass, field


@dataclass
class ScraperResult:
    """Return type for all scraper run functions.

    Tracks counts of listings processed at each pipeline stage and
    any error messages encountered during the run.
    """

    source: str
    listings_found: int = 0
    listings_inserted: int = 0
    listings_skipped: int = 0
    listings_rejected: int = 0
    listings_flagged: int = 0
    errors: list[str] = field(default_factory=list)
    success: bool = True
