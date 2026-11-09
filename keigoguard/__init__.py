"""JP Keigo Guard: find double honorifics (二重敬語) and mismatched honorific chains in AI-written Japanese, by the rules of 「敬語の指針」."""
from .guard import ACCEPTED, GUIDELINE, GUIDELINE_URL, check, fix

__version__ = "0.1.0"
__all__ = ["check", "fix", "ACCEPTED", "GUIDELINE", "GUIDELINE_URL", "__version__"]
