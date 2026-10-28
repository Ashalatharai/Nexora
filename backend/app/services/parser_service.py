import re
from typing import List, Tuple
from app.schemas.chat import ChatStructuredAction, ActionDomain


class MessageParserFallback:
    """
    Decoupled rule-based / regex parser fallback.
    Used when the frontend or user submits a raw message without pre-parsed actions.
    Translates natural-language shopkeeper sentences into ChatStructuredAction objects.
    """

    @staticmethod
    def parse_message(raw_text: str) -> Tuple[List[ChatStructuredAction], str]:
        """
        Parses text and returns (structured_actions, detected_intent).
        Supported intents: 'inventory', 'credit', 'unrecognized'.
        """
        text = raw_text.strip().lower()
        actions: List[ChatStructuredAction] = []

        # 1. Check for Credit: Payment (e.g., "ramesh paid ₹200", "ramesh paid 200", "received 500 from ramesh")
        payment_match = (
            re.search(r"([a-z\s]+?)\s+(?:paid|cleared|deposited)\s+[₹rs.]*\s*([0-9]+(?:\.[0-9]+)?)", text) or
            re.search(r"(?:received|got)\s+[₹rs.]*\s*([0-9]+(?:\.[0-9]+)?)\s+(?:from)\s+([a-z\s]+)", text)
        )
        if payment_match:
            if payment_match.re.pattern.startswith("([a-z"):
                customer_name = payment_match.group(1).strip().title()
                amount = float(payment_match.group(2))
            else:
                amount = float(payment_match.group(1))
                customer_name = payment_match.group(2).strip().title()

            actions.append(
                ChatStructuredAction(
                    domain=ActionDomain.CREDIT,
                    action="payment",
                    customer_name=customer_name,
                    amount=amount
                )
            )
            return actions, "credit"

        # 2. Check for Credit: Purchase / Udhaar (e.g. "ramesh took 200 on credit", "ramesh credit 500", "udhaar ramesh 300", "ramesh took 2 rice on credit")
        credit_amount_match = re.search(
            r"([a-z\s]+?)\s+(?:took|borrowed)?\s*[₹rs.]*\s*([0-9]+(?:\.[0-9]+)?)\s*(?:on\s+credit|udhaar)",
            text
        )
        if credit_amount_match:
            customer_name = credit_amount_match.group(1).replace("took", "").replace("udhaar", "").strip().title()
            amount = float(credit_amount_match.group(2))
            actions.append(
                ChatStructuredAction(
                    domain=ActionDomain.CREDIT,
                    action="credit_purchase",
                    customer_name=customer_name,
                    amount=amount
                )
            )
            return actions, "credit"

        # 3. Check for Inventory Actions:
        # e.g., "sold 3 maggi, 2 milk", "received 20 rice bags", "damaged 1 oil", "returned 2 soap"
        # Determine overall action or per-clause action
        action_keywords = {
            "sold": "sold",
            "sell": "sold",
            "sale": "sold",
            "received": "received",
            "got": "received",
            "bought": "received",
            "purchased": "received",
            "damaged": "damaged",
            "damage": "damaged",
            "waste": "damaged",
            "returned": "returned",
            "return": "returned",
        }

        # Check if message starts with an action or has action verbs
        # Split by comma or "and" for multi-item clauses
        clauses = re.split(r"[,&]|\band\b", text)
        current_action = None

        for clause in clauses:
            clause = clause.strip()
            if not clause:
                continue

            # Check if this clause specifies a new action
            words = clause.split()
            first_word = words[0] if words else ""
            if first_word in action_keywords:
                current_action = action_keywords[first_word]
                # Remove action keyword from clause
                clause = " ".join(words[1:])
            elif current_action is None:
                for k, v in action_keywords.items():
                    if k in clause:
                        current_action = v
                        clause = clause.replace(k, "").strip()
                        break

            if not current_action:
                current_action = "sold"  # default kirana shopkeeper intent is sales

            # Match pattern: <quantity> <item_name> [unit]
            # e.g., "3 maggi", "20 rice bags", "1 oil"
            item_match = re.search(r"([0-9]+(?:\.[0-9]+)?)\s+([a-z0-9\s]+)", clause)
            if item_match:
                qty = float(item_match.group(1))
                item_raw = item_match.group(2).strip()

                # Clean common trailing units if present
                units = ["bags", "bag", "packets", "packet", "pkts", "pkt", "bottles", "bottle", "bars", "bar", "kg", "kgs", "litres", "litre", "l"]
                detected_unit = None
                tokens = item_raw.split()
                if len(tokens) > 1 and tokens[-1] in units:
                    detected_unit = tokens[-1]
                    item_name = " ".join(tokens[:-1])
                else:
                    item_name = item_raw

                actions.append(
                    ChatStructuredAction(
                        domain=ActionDomain.INVENTORY,
                        action=current_action,
                        item_name=item_name.strip(),
                        quantity=qty,
                        unit=detected_unit
                    )
                )

        if actions:
            return actions, "inventory"

        return [], "unrecognized"
