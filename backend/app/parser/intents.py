import re
from typing import List, Tuple, Optional
from app.schemas.chat import ChatStructuredAction, ActionDomain
from app.parser.entities import EntityExtractor


class IntentParser:
    @staticmethod
    def parse_credit_payment(text: str) -> Optional[ChatStructuredAction]:
        """
        Parses customer payments:
        - "Ramesh paid 200"
        - "received 500 from Ramesh"
        - "Ramesh repaid 300"
        - "Ramesh paid ₹200"
        """
        # Pattern A: <customer> paid/repaid/cleared ₹?<amount>
        match_a = re.search(r"([a-z\s]+?)\s+(?:paid|repaid|cleared|deposited)\s+[₹]?\s*([0-9]+(?:\.[0-9]+)?)", text)
        if match_a:
            customer = EntityExtractor.clean_customer_name(match_a.group(1))
            amount = float(match_a.group(2))
            if amount > 0 and customer:
                return ChatStructuredAction(
                    domain=ActionDomain.CREDIT,
                    action="payment",
                    customer_name=customer,
                    amount=amount
                )

        # Pattern B: received ₹?<amount> from <customer>
        match_b = re.search(r"(?:received|got)\s+[₹]?\s*([0-9]+(?:\.[0-9]+)?)\s+from\s+([a-z\s]+)", text)
        if match_b:
            amount = float(match_b.group(1))
            customer = EntityExtractor.clean_customer_name(match_b.group(2))
            if amount > 0 and customer:
                return ChatStructuredAction(
                    domain=ActionDomain.CREDIT,
                    action="payment",
                    customer_name=customer,
                    amount=amount
                )

        return None

    @staticmethod
    def parse_credit_item_purchase(text: str) -> Optional[ChatStructuredAction]:
        """
        Parses credit purchases of items:
        - "Ramesh took 2 rice on credit"
        - "give Ramesh 3 soaps on udhaar"
        - "Ramesh bought 5 items on credit"
        """
        match = re.search(
            r"([a-z\s]+?)\s+(?:took|bought|purchased|got|give)\s+([0-9]+(?:\.[0-9]+)?)\s+([a-z0-9\s]+?)\s+(?:on\s+credit|on\s+udhaar|in\s+udhaar|udhaar)",
            text
        )
        if match:
            customer = EntityExtractor.clean_customer_name(match.group(1))
            qty = float(match.group(2))
            raw_item = match.group(3).strip()
            item, unit = EntityExtractor.extract_item_and_unit(raw_item)
            if qty > 0 and customer and item:
                return ChatStructuredAction(
                    domain=ActionDomain.CREDIT,
                    action="credit_purchase",
                    customer_name=customer,
                    item_name=item,
                    quantity=qty,
                    unit=unit
                )
        return None

    @staticmethod
    def parse_credit_direct_amount(text: str) -> Optional[ChatStructuredAction]:
        """
        Parses direct credit amounts:
        - "Ramesh took 500 on credit"
        - "udhaar Ramesh 300"
        - "Ramesh credit 200"
        """
        # Pattern A: <customer> took/borrowed ₹?<amount> on credit/udhaar
        match = re.search(
            r"([a-z\s]+?)\s+(?:took|borrowed)\s+[₹]?\s*([0-9]+(?:\.[0-9]+)?)\s*(?:on\s+credit|on\s+udhaar|udhaar|credit)",
            text
        )
        if match:
            raw_name = match.group(1).strip()
            customer = EntityExtractor.clean_customer_name(raw_name)
            amount = float(match.group(2))
            if amount > 0 and customer and not customer.isdigit():
                return ChatStructuredAction(
                    domain=ActionDomain.CREDIT,
                    action="credit_purchase",
                    customer_name=customer,
                    amount=amount
                )

        # Pattern B: udhaar/credit <customer> ₹?<amount>
        match_prefix = re.search(
            r"(?:udhaar|credit)\s+([a-z\s]+?)\s+[₹]?\s*([0-9]+(?:\.[0-9]+)?)",
            text
        )
        if match_prefix:
            customer = EntityExtractor.clean_customer_name(match_prefix.group(1))
            amount = float(match_prefix.group(2))
            if amount > 0 and customer and not customer.isdigit():
                return ChatStructuredAction(
                    domain=ActionDomain.CREDIT,
                    action="credit_purchase",
                    customer_name=customer,
                    amount=amount
                )

        # Pattern C: <customer> credit/udhaar ₹?<amount>
        match_suffix = re.search(
            r"([a-z\s]+?)\s+(?:credit|udhaar)\s+[₹]?\s*([0-9]+(?:\.[0-9]+)?)",
            text
        )
        if match_suffix:
            customer = EntityExtractor.clean_customer_name(match_suffix.group(1))
            amount = float(match_suffix.group(2))
            if amount > 0 and customer and not customer.isdigit():
                return ChatStructuredAction(
                    domain=ActionDomain.CREDIT,
                    action="credit_purchase",
                    customer_name=customer,
                    amount=amount
                )

        return None

    @staticmethod
    def parse_inventory_clauses(text: str) -> List[ChatStructuredAction]:
        """
        Parses single or multi-item inventory clauses:
        - "sold 3 maggi, 2 milk"
        - "sold 5 soaps and 3 shampoos"
        - "received 20 rice bags"
        - "damaged 2 oil bottles"
        - "customer returned 2 soaps"
        """
        action_map = {
            "sold": "sold",
            "sell": "sold",
            "sale": "sold",
            "received": "received",
            "receive": "received",
            "bought": "received",
            "purchased": "received",
            "added": "received",
            "damaged": "damaged",
            "damage": "damaged",
            "waste": "damaged",
            "expired": "damaged",
            "broken": "damaged",
            "returned": "returned",
            "return": "returned",
        }

        actions: List[ChatStructuredAction] = []
        clauses = re.split(r"[,&]|\band\b", text)
        current_action = None

        for clause in clauses:
            clause = clause.strip()
            if not clause:
                continue

            words = clause.split()
            first_word = words[0] if words else ""

            if first_word in action_map:
                current_action = action_map[first_word]
                clause = " ".join(words[1:])
            elif current_action is None:
                for k, v in action_map.items():
                    if k in words:
                        current_action = v
                        clause = " ".join([w for w in words if w != k])
                        break

            if not current_action:
                current_action = "sold"  # default kirana shopkeeper context

            # Extract pattern: <quantity> <item_name_with_optional_unit>
            match = re.search(r"([0-9]+(?:\.[0-9]+)?)\s+([a-z0-9\s]+)", clause)
            if match:
                qty = float(match.group(1))
                raw_item = match.group(2).strip()
                item, unit = EntityExtractor.extract_item_and_unit(raw_item)
                if qty > 0 and item:
                    actions.append(
                        ChatStructuredAction(
                            domain=ActionDomain.INVENTORY,
                            action=current_action,
                            item_name=item,
                            quantity=qty,
                            unit=unit
                        )
                    )

        return actions
