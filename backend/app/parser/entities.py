from typing import Tuple, Optional
from app.parser.vocabulary import KNOWN_UNITS, PLURAL_TO_SINGULAR, ITEM_ALIASES


class EntityExtractor:
    @staticmethod
    def extract_item_and_unit(raw_text: str) -> Tuple[str, Optional[str]]:
        """
        Cleans grocery item name:
        1. Strips detected unit words from suffix or prefix.
        2. Normalizes plural words (soaps -> soap, shampoos -> shampoo).
        3. Looks up canonical name in ITEM_ALIASES.
        """
        tokens = raw_text.strip().lower().split()
        if not tokens:
            return "", None

        detected_unit = None

        # Check if last token is a known unit
        if tokens[-1] in KNOWN_UNITS:
            detected_unit = KNOWN_UNITS[tokens[-1]]
            tokens = tokens[:-1]
        # Check if first token is a known unit
        elif tokens[0] in KNOWN_UNITS and len(tokens) > 1:
            detected_unit = KNOWN_UNITS[tokens[0]]
            tokens = tokens[1:]

        cleaned_item = " ".join(tokens).strip()

        # Check singular mapping for whole phrase or words
        if cleaned_item in PLURAL_TO_SINGULAR:
            cleaned_item = PLURAL_TO_SINGULAR[cleaned_item]
        else:
            # Check individual tokens
            word_tokens = [PLURAL_TO_SINGULAR.get(t, t) for t in cleaned_item.split()]
            cleaned_item = " ".join(word_tokens)

        # Look up in ITEM_ALIASES
        canonical = ITEM_ALIASES.get(cleaned_item, cleaned_item)

        return canonical, detected_unit

    @staticmethod
    def clean_customer_name(raw_name: str) -> str:
        """Clean customer name (strips honorifics and title-cases)."""
        tokens = raw_name.strip().split()
        filtered = [t for t in tokens if t.lower() not in {"mr", "mrs", "ji", "bhai", "bhaiya", "customer", "shri"}]
        name = " ".join(filtered).strip()
        return name.title() if name else raw_name.strip().title()
