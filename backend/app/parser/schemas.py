from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field
from app.schemas.chat import ChatStructuredAction, ActionDomain


class AmbiguityType(str, Enum):
    NONE = "none"
    MISSING_QUANTITY = "missing_quantity"
    MISSING_ITEM = "missing_item"
    MISSING_ACTION = "missing_action"
    MISSING_CUSTOMER = "missing_customer"
    MISSING_AMOUNT = "missing_amount"
    INVALID_NUMBER = "invalid_number"
    UNRECOGNIZED = "unrecognized"


class ParseResult(BaseModel):
    raw_message: str
    clean_message: str
    intent: str  # "inventory", "credit", "ambiguous", "unrecognized"
    success: bool
    actions: List[ChatStructuredAction] = []
    is_ambiguous: bool = False
    ambiguity_type: AmbiguityType = AmbiguityType.NONE
    clarification_prompt: Optional[str] = None
