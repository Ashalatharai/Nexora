import re
from app.parser.vocabulary import WORD_TO_NUMBER


class TextNormalizer:
    @staticmethod
    def normalize(text: str) -> str:
        if not text:
            return ""

        # 1. Lowercase and strip
        s = text.strip().lower()

        # 2. Currency symbol normalization
        # e.g. "rs. 500", "rs 500", "inr 500", "500 rupees", "500 rs", "500 inr"
        s = re.sub(r"(?:rs\.?|inr)\s*([0-9]+(?:\.[0-9]+)?)", r"₹\1", s)
        s = re.sub(r"([0-9]+(?:\.[0-9]+)?)\s*(?:rupees|rs\.?|inr)", r"₹\1", s)

        # 3. Replace word numbers with digits if followed by space/word
        for word, num in WORD_TO_NUMBER.items():
            s = re.sub(rf"\b{word}\b", str(int(num) if num.is_integer() else num), s)

        # 4. Phrasing standardizations
        # "added 10 milk packets to stock" -> "received 10 milk packets"
        s = re.sub(r"\badded\s+(.*?)\s+(?:to\s+stock|in\s+stock)\b", r"received \1", s)

        # "2 biscuits were damaged" / "1 oil was damaged" -> "damaged 2 biscuits"
        damaged_passive = re.search(r"([0-9]+(?:\.[0-9]+)?\s+[a-z\s]+?)\s+(?:was|were)\s+damaged", s)
        if damaged_passive:
            s = f"damaged {damaged_passive.group(1).strip()}"

        # "customer returned 2 soaps" -> "returned 2 soaps"
        s = re.sub(r"\bcustomer\s+returned\b", "returned", s)

        # "give ramesh 3 soaps on udhaar" -> "ramesh took 3 soaps on udhaar"
        s = re.sub(r"\bgive\s+([a-z\s]+?)\s+([0-9]+(?:\.[0-9]+)?\s+[a-z\s]+?)\s+(?:on\s+udhaar|on\s+credit)\b", r"\1 took \2 on credit", s)

        # "i sold 4 rice bags" -> "sold 4 rice bags"
        s = re.sub(r"\bi\s+(?:sold|sell)\b", "sold", s)

        # "repaid 300" / "returned 300" for money -> "paid 300"
        s = re.sub(r"\brepaid\b", "paid", s)

        # 5. Clean extra spaces and punctuation
        s = re.sub(r"[!?;]", "", s)
        s = re.sub(r"\s+", " ", s).strip()

        return s
