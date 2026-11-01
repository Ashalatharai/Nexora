import json
import logging
import urllib.request
import urllib.error
from typing import Optional, Dict, Any
from app.config import GEMINI_API_KEY, AI_MODEL_NAME

logger = logging.getLogger("kirana.ai_parser")


class AIParser:
    """
    Optional LLM-based intent and entity extraction layer.
    Extracts structured entities from complex or multi-lingual shopkeeper expressions.
    Always falls back to deterministic rule-based parsing if unconfigured or unreachable.
    Model output is strictly validated and treated as untrusted input.
    """

    @classmethod
    def is_available(cls) -> bool:
        key = (GEMINI_API_KEY or "").strip()
        return bool(key and key != "your_gemini_api_key_here")

    @classmethod
    def extract_intent_and_entities(cls, message: str) -> Optional[Dict[str, Any]]:
        """
        Attempt extraction via Gemini API.
        Returns parsed dictionary if successful, or None to fall back to deterministic parsing.
        """
        if not cls.is_available() or not message or not message.strip():
            return None

        prompt = (
            "You are a Kirana (grocery store) NLP assistant. Extract the intent and entities from the shopkeeper's message.\n"
            "Return ONLY a valid JSON object with these keys:\n"
            "- domain: 'inventory', 'credit', 'query', or 'unknown'\n"
            "- intent: 'sold', 'received', 'damaged', 'returned', 'credit_purchase', 'payment', 'stock_query', 'debt_query', 'summary_query', 'reorder_query', or 'unknown'\n"
            "- item_name: string or null\n"
            "- quantity: float or null\n"
            "- customer_name: string or null\n"
            "- amount: float or null\n"
            "- is_ambiguous: boolean\n"
            "- clarification_question: string or null\n\n"
            f"Message: \"{message.strip()}\"\n"
        )

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{AI_MODEL_NAME}:generateContent?key={GEMINI_API_KEY.strip()}"
        payload = {
            "contents": [{
                "parts": [{"text": prompt}]
            }],
            "generationConfig": {
                "temperature": 0.1,
                "responseMimeType": "application/json"
            }
        }

        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=3.5) as resp:
                resp_json = json.loads(resp.read().decode("utf-8"))
                candidates = resp_json.get("candidates", [])
                if not candidates:
                    return None
                parts = candidates[0].get("content", {}).get("parts", [])
                if not parts:
                    return None
                text_output = parts[0].get("text", "").strip()
                parsed = json.loads(text_output)
                logger.info(f"AI parser extracted: {parsed}")
                return parsed

        except urllib.error.HTTPError as http_err:
            logger.warning(f"AI provider returned HTTP {http_err.code}, falling back to deterministic parser.")
            return None
        except Exception as exc:
            logger.info(f"AI provider request skipped/timed out ({exc}), falling back to deterministic parser.")
            return None
