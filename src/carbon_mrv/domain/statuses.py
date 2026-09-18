from enum import StrEnum


class CreditsStatus(StrEnum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"


class Confidence(StrEnum):
    CONFIRMED = "confirmed"
    PROBABLE = "probable"
    UNCERTAIN = "uncertain"


class CauseStatus(StrEnum):
    ESTABLISHED = "established"
    NOT_ESTABLISHED = "cause_not_established"
