from fastapi import APIRouter
from app.parser import KiranaMessageParser, ParseResult
from app.schemas.chat import ChatRequest

router = APIRouter(prefix="/parser", tags=["Message Parser"])


@router.post("/parse", response_model=ParseResult, summary="Parse natural language message into structured actions")
def parse_shopkeeper_message(request: ChatRequest):
    """
    Direct endpoint for the message parser:
    Translates raw natural language grocery shop messages into structured actions
    or actionable clarification requests.
    """
    return KiranaMessageParser.parse(request.message or "")
