import re
from typing import List, Tuple
from app.schemas.chat import ChatStructuredAction, ActionDomain
from app.models.inventory import ITEM_ALIASES


class MessageParserFallback:
    """
    Decoupled rule-based / regex parser fallback.
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

        # 1. Check for Credit: Payment (e.g. "Ramesh paid ₹200", "Ramesh paid 200", "received 500 from Ramesh")
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

        # 2. Check for Credit Sale of Items: e.g. "Ramesh took 2 rice on credit", "Ramesh bought 3 maggi on udhaar"
        credit_item_match = re.search(
            r"([a-z\s]+?)\s+(?:took|bought|purchased|got)\s+([0-9]+(?:\.[0-9]+)?)\s+([a-z0-9\s]+?)\s+(?:on\s+credit|on\s+udhaar|in\s+udhaar|udhaar)",
            text
        )
        if credit_item_match:
            customer_name = credit_item_match.group(1).strip().title()
            qty = float(credit_item_match.group(2))
            item_raw = credit_item_match.group(3).strip()

            # Clean trailing unit
            units = ["bags", "bag", "packets", "packet", "pkts", "pkt", "bottles", "bottle", "bars", "bar", "kg", "kgs", "litres", "litre", "l"]
            tokens = item_raw.split()
            if len(tokens) > 1 and tokens[-1] in units:
                item_name = " ".join(tokens[:-1])
                unit = tokens[-1]
            else:
                item_name = item_raw
                unit = None

            canonical_name = ITEM_ALIASES.get(item_name.lower(), item_name.lower())

            actions.append(
                ChatStructuredAction(
                    domain=ActionDomain.CREDIT,
                    action="credit_purchase",
                    customer_name=customer_name,
                    item_name=canonical_name,
                    quantity=qty,
                    unit=unit
                )
            )
            return actions, "credit"

        # 3. Check for Direct Credit Amount: e.g. "Ramesh took 200 on credit", "Ramesh credit 500", "udhaar Ramesh 300"
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

        # 4. Check for Inventory Actions: e.g. "sold 3 maggi, 2 milk", "received 20 rice bags", "damaged 1 oil"
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

        clauses = re.split(r"[,&]|\band\b", text)
        current_action = None

        for clause in clauses:
            clause = clause.strip()
            if not clause:
                continue

            words = clause.split()
            first_word = words[0] if words else ""
            if first_word in action_keywords:
                current_action = action_keywords[first_word]
                clause = " ".join(words[1:])
            elif current_action is None:
                for k, v in action_keywords.items():
                    if k in clause:
                        current_action = v
                        clause = clause.replace(k, "").strip()
                        break

            if not current_action:
                current_action = "sold"

            item_match = re.search(r"([0-9]+(?:\.[0-9]+)?)\s+([a-z0-9\s]+)", clause)
            if item_match:
                qty = float(item_match.group(1))
                item_raw = item_match.group(2).strip()

                units = ["bags", "bag", "packets", "packet", "pkts", "pkt", "bottles", "bottle", "bars", "bar", "kg", "kgs", "litres", "litre", "l"]
                detected_unit = None
                tokens = item_raw.split()
                if len(tokens) > 1 and tokens[-1] in units:
                    detected_unit = tokens[-1]
                    item_name = " ".join(tokens[:-1])
                else:
                    item_name = item_raw

                canonical_name = ITEM_ALIASES.get(item_name.lower(), item_name.lower())

                actions.append(
                    ChatStructuredAction(
                        domain=ActionDomain.INVENTORY,
                        action=current_action,
                        item_name=canonical_name,
                        quantity=qty,
                        unit=detected_unit
                    )
                )

        if actions:
            return actions, "inventory"

        return [], "unrecognized"
