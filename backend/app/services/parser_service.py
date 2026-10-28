from typing import List, Tuple
from app.schemas.chat import ChatStructuredAction
from app.parser import KiranaMessageParser, ParseResult


class MessageParserFallback:
    """
    Service adapter for the KiranaMessageParser.
    Provides backward-compatible interface for routers and services.
    """

    @staticmethod
    def parse_message(raw_text: str) -> Tuple[List[ChatStructuredAction], str]:
        """
        Parses text using the KiranaMessageParser engine.
        Returns (structured_actions, detected_intent).
        """
        result: ParseResult = KiranaMessageParser.parse(raw_text)
        if result.success and result.actions:
            return result.actions, result.intent
        return [], result.intent

    @staticmethod
    def parse_with_details(raw_text: str) -> ParseResult:
        """Full parse result with ambiguity detection and clarification prompts."""
        return KiranaMessageParser.parse(raw_text)
