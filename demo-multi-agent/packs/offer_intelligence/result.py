"""Shared data models for offer unpublish validation results."""
from enum import Enum
from dataclasses import dataclass, field


class ValidationStatus(Enum):
    VALID = "Valid ✅"
    INVALID = "Invalid (needs review) ❌"
    UNKNOWN_REASON = "Unpublish reason code not part of list ❓"
    NEEDS_MANUAL_REVIEW = "Needs Manual Review 🛠️"
    NOT_IMPLEMENTED = "Validator not yet implemented 🚧"
    NO_REVIEW_REQUIRED = "No review required ✅"


@dataclass
class ValidationResult:
    offer_id: str
    reason_code: str
    status: ValidationStatus
    message: str
    details: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "offer_id": self.offer_id,
            "reason_code": self.reason_code,
            "status": self.status.value,
            "message": self.message,
            "details": self.details,
        }
