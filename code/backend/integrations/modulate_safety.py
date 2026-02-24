from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import List


class SafetyCategory(str, Enum):
    NONE = "none"


@dataclass
class SafetyScreenResult:
    campaign_id: str
    blocked: bool = False
    toxicity_score: float = 0.0
    categories: List[SafetyCategory] = None
    screening_method: str = "disabled"
    latency_ms: float = 0.0

    def __post_init__(self) -> None:
        if self.categories is None:
            self.categories = [SafetyCategory.NONE]


def screen_campaign(
    campaign_id: str,
    headline: str,
    body_copy: str,
    company_id: str,
) -> SafetyScreenResult:
    return SafetyScreenResult(campaign_id=campaign_id)
