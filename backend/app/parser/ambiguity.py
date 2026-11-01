import re
from typing import Optional, Tuple, Any
from app.parser.schemas import AmbiguityType


class AmbiguityDetector:
    @staticmethod
    def check_ambiguity(clean_text: str, context: Any = None) -> Tuple[bool, AmbiguityType, Optional[str]]:
        """
        Detects ambiguous or incomplete messages that should prompt for clarification
        instead of making assumptions or fabricating data.
        """
        text = clean_text.strip().lower()

        if not text:
            return True, AmbiguityType.UNRECOGNIZED, "Empty message. Please enter a transaction (e.g. 'sold 3 maggi', 'Ramesh paid 200')."

        # 1. Invalid / zero / negative numbers
        neg_zero_match = re.search(r"\b(?:sold|received|damaged|returned|paid|credit)\s+(-[0-9]+|0(?:\.0+)?)\b", text)
        if neg_zero_match:
            return True, AmbiguityType.INVALID_NUMBER, "Quantities and payment amounts must be greater than zero."

        # 2. Ambiguous quantity words ("some", "few", "lot", "little")
        some_match = re.search(r"\b(sold|received|damaged|returned)\s+(?:some|a\s+few|few|lot\s+of)\s+([a-z\s]+)", text)
        if some_match:
            action = some_match.group(1)
            item = some_match.group(2).strip()
            return True, AmbiguityType.MISSING_QUANTITY, f"Please specify the exact quantity of {item} {action} (e.g. '{action} 2 {item}')."

        # 3. Action with item but no quantity: e.g. "sold rice", "received milk"
        no_qty_action = re.fullmatch(r"(sold|received|damaged|returned)\s+([a-z]+)", text)
        if no_qty_action:
            action = no_qty_action.group(1)
            item = no_qty_action.group(2)
            if item not in ["stock", "goods", "items"]:
                return True, AmbiguityType.MISSING_QUANTITY, f"Please specify the quantity of {item} to {action} (e.g. '{action} 2 {item}')."

        # 4. Action without item and quantity: e.g. "add stock", "stock received", "update stock"
        if text in ["add stock", "stock received", "received stock", "update inventory", "update stock", "sold items"]:
            return True, AmbiguityType.MISSING_ITEM, "Please specify the item and quantity (e.g. 'received 20 rice bags' or 'sold 3 maggi')."

        # 5. Customer paid with missing amount: e.g. "ramesh paid", "paid by ramesh", "received from ramesh"
        paid_no_amount = (
            re.fullmatch(r"([a-z]+)\s+paid", text) or
            re.fullmatch(r"received\s+(?:money\s+)?from\s+([a-z]+)", text) or
            re.fullmatch(r"paid\s+by\s+([a-z]+)", text)
        )
        if paid_no_amount:
            customer = paid_no_amount.group(1).title()
            return True, AmbiguityType.MISSING_AMOUNT, f"Please specify the amount {customer} paid (e.g. '{customer} paid ₹200')."

        # 6. Customer credit with missing amount/items: e.g. "ramesh on credit", "udhaar ramesh"
        credit_no_amount = (
            re.fullmatch(r"([a-z]+)\s+(?:on\s+credit|on\s+udhaar|took\s+credit)", text) or
            re.fullmatch(r"(?:udhaar|credit)\s+([a-z]+)", text)
        )
        if credit_no_amount:
            customer = credit_no_amount.group(1).title()
            return True, AmbiguityType.MISSING_AMOUNT, f"Please specify what {customer} took on credit or the amount (e.g. '{customer} took 2 rice on credit' or '{customer} took 500 on credit')."

        # 7. Quantity and item without action: e.g. "3 maggi", "2 milk packets"
        qty_item_no_action = re.fullmatch(r"([0-9]+(?:\.[0-9]+)?)\s+([a-z\s]+)", text)
        if qty_item_no_action:
            qty = qty_item_no_action.group(1)
            item = qty_item_no_action.group(2).strip()
            # If not a standalone phone number or date
            if not item.isdigit() and len(item) > 1 and item not in ["sold", "received", "damaged", "returned"]:
                return True, AmbiguityType.MISSING_ACTION, f"Did you sell, receive, or damage {qty} {item}? (e.g. 'sold {qty} {item}')."

        # 8. Action + quantity without item (e.g. "sell 5", "sold 5") when NO context item is present
        action_qty_no_item = re.fullmatch(r"(sold|sell|received|receive|damaged|returned)\s+([0-9]+(?:\.[0-9]+)?)", text)
        if action_qty_no_item:
            if not (context and getattr(context, "last_item_name", None)):
                act = action_qty_no_item.group(1)
                qty = action_qty_no_item.group(2)
                return True, AmbiguityType.MISSING_ITEM, f"Please specify which item you want to {act} (e.g. '{act} {qty} rice')."

        # 9. Payment without customer name (e.g. "paid 200", "he paid 200") when NO context customer is present
        pay_no_customer = re.fullmatch(r"(?:he\s+|she\s+)?(?:paid|repaid|cleared)\s+[₹]?\s*([0-9]+(?:\.[0-9]+)?)", text)
        if pay_no_customer:
            if not (context and getattr(context, "last_customer_name", None)):
                amt = pay_no_customer.group(1)
                return True, AmbiguityType.MISSING_CUSTOMER, f"Please specify who made the payment of ₹{amt} (e.g. 'Ramesh paid {amt}')."

        return False, AmbiguityType.NONE, None
