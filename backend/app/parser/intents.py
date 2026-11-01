import re
from typing import List, Tuple, Optional, Any
from app.schemas.chat import ChatStructuredAction, ActionDomain
from app.parser.entities import EntityExtractor

ALLOWED_UNITS = r"(?:packets?|pkts?|kg|litres?|l|ml|bottles?|bags?|box(?:es)?|pcs|pieces?)"
PRONOUNS = {"he", "she", "they", "him", "her", "them", "someone", "customer", "who", "it", "that", "this"}


class IntentParser:
    @staticmethod
    def parse_query(text: str) -> Optional[ChatStructuredAction]:
        """
        Parses read-only inquiry intents:
        - Stock inquiry: "How much rice do I have?", "rice stock", "check stock of milk", "is maggi available?"
        - Low stock alerts: "What items are low on stock?", "low stock items", "show alerts", "what needs reordering?"
        - Daily summary: "What were today's sales?", "today's summary", "how much did I sell today?", "daily report"
        - Customer balance: "How much does Ramesh owe?", "Ramesh balance", "check udhaar for Ramesh"
        - All udhaar list: "Who owes money?", "show all udhaar", "list credit customers", "total udhaar"
        - Reorder draft: "Reorder rice", "draft reorder for milk", "reorder stock"
        - Confirmations: "yes", "confirm", "proceed", "haan", "ok"
        - Cancellations: "no", "cancel", "abort", "nah", "mat karo", "don't"
        """
        clean = text.strip().lower()

        # 1. Confirmations & Cancellations
        if clean in ["yes", "yep", "yeah", "confirm", "proceed", "haan", "sure", "correct", "do it", "ha", "ok", "okay"]:
            return ChatStructuredAction(domain=ActionDomain.QUERY, action="confirm")

        if clean in ["no", "nope", "cancel", "stop", "abort", "nah", "mat karo", "don't", "dont", "dont do it", "cancel that"]:
            return ChatStructuredAction(domain=ActionDomain.QUERY, action="cancel")

        # 2. Daily Summary
        if re.search(r"\b(?:today(?:'s)?\s+(?:sales|summary|report|collection)|daily\s+(?:sales|summary|report)|how much (?:did i|was)\s+sold today|total sales today|day summary)\b", clean):
            return ChatStructuredAction(domain=ActionDomain.QUERY, action="daily_summary")

        # 3. Low Stock & Out of Stock Alerts
        if re.search(r"\b(?:low\s+stock(?:s)?(?:\s+items|\s+alerts)?|what(?:'s|\s+is|\s+items\s+are)?\s+low\s+on\s+stock|show\s+alerts|what\s+needs\s+reordering|which\s+items\s+are\s+out\s+of\s+stock|out\s+of\s+stock\s+items|stock\s+alerts?)\b", clean):
            return ChatStructuredAction(domain=ActionDomain.QUERY, action="low_stock")

        # 4. All Udhaar / Credit Customers List
        if re.search(r"\b(?:who\s+owes\s+money|show\s+(?:all\s+)?udhaar|list\s+(?:all\s+)?credit|all\s+credit\s+balances|total\s+udhaar|udhaar\s+list|pending\s+(?:udhaar|credit))\b", clean):
            return ChatStructuredAction(domain=ActionDomain.QUERY, action="all_udhaar")

        # 5. Customer Balance Inquiry: e.g. "How much does Ramesh owe?", "Ramesh balance", "check udhaar for Ramesh"
        match_cust_owe = re.search(
            r"(?:how much (?:does|is)\s+([a-z\s]+?)\s+(?:owe|have in udhaar)|how much (?:is\s+)?([a-z\s]+?)'?s?\s+(?:balance|udhaar|debt)|(?:check|show|get)\s+(?:balance|udhaar)\s+(?:of|for)\s+([a-z\s]+)|([a-z\s]+?)\s+(?:balance|udhaar))",
            clean
        )
        if match_cust_owe:
            raw_cust = match_cust_owe.group(1) or match_cust_owe.group(2) or match_cust_owe.group(3) or match_cust_owe.group(4)
            if raw_cust:
                customer = EntityExtractor.clean_customer_name(raw_cust)
                # Ignore non-names, pronouns, or generic keywords
                if customer and customer.lower() not in PRONOUNS and customer.lower() not in ["all", "total", "today", "yesterday", "stock", "sales", "shop", "items"]:
                    return ChatStructuredAction(
                        domain=ActionDomain.QUERY,
                        action="customer_balance",
                        customer_name=customer
                    )

        # 6. Reorder Draft: e.g. "reorder rice", "draft reorder for milk", "reorder 10 rice"
        match_reorder = re.search(
            r"(?:reorder|draft\s+reorder\s+(?:for\s+)?|order\s+stock\s+(?:for\s+)?)\s*(?:([0-9]+(?:\.[0-9]+)?)\s+)?([a-z0-9\s]+)",
            clean
        )
        if match_reorder:
            qty_str = match_reorder.group(1)
            raw_item = match_reorder.group(2).strip()
            item, unit = EntityExtractor.extract_item_and_unit(raw_item)
            qty = float(qty_str) if qty_str else None
            if item:
                return ChatStructuredAction(
                    domain=ActionDomain.QUERY,
                    action="reorder_draft",
                    item_name=item,
                    quantity=qty,
                    unit=unit
                )

        # 7. Item Stock Inquiry: e.g. "How much rice do I have?", "check stock of milk", "is maggi available?", "rice stock"
        match_stock = re.search(
            r"(?:how (?:much|many)\s+([a-z0-9\s]+?)\s+(?:do i have|is left|left|in stock|available|do we have)|(?:check|show|get|what is the)\s+stock\s+(?:of|for)\s+([a-z0-9\s]+)|([a-z0-9\s]+?)\s+stock|is\s+([a-z0-9\s]+?)\s+available|do i have\s+([a-z0-9\s]+))",
            clean
        )
        if match_stock:
            raw_item = match_stock.group(1) or match_stock.group(2) or match_stock.group(3) or match_stock.group(4) or match_stock.group(5)
            if raw_item:
                item, unit = EntityExtractor.extract_item_and_unit(raw_item.strip())
                if item and item not in ["low", "out of", "update", "add"]:
                    return ChatStructuredAction(
                        domain=ActionDomain.QUERY,
                        action="stock_item",
                        item_name=item,
                        unit=unit
                    )

        return None

    @staticmethod
    def parse_contextual_followup(text: str, context: Any) -> Optional[ChatStructuredAction]:
        """
        Parses contextual follow-up messages that rely on previous conversation turns:
        - Missing item follow-up: "sell 5", "sold 5", "damaged 2", "received 20" -> uses context.last_item_name
        - Missing customer follow-up: "he paid 200", "paid 200", "cleared 200" -> uses context.last_customer_name
        - Credit item follow-up: "he took 2 on credit" -> uses both context.last_customer_name and context.last_item_name
        """
        if not context:
            return None

        clean = text.strip().lower()

        # A. Customer repayment follow-up: "he paid 200", "paid 200", "cleared 200", "he gave 200"
        if getattr(context, "last_customer_name", None):
            match_pay = re.search(
                r"^(?:he|she|they)?\s*(?:paid|repaid|cleared|gave|deposited)\s+[₹]?\s*([0-9]+(?:\.[0-9]+)?)$",
                clean
            )
            if not match_pay:
                match_pay = re.search(r"^received\s+[₹]?\s*([0-9]+(?:\.[0-9]+)?)(?:\s+from\s+(?:him|her|them))?$", clean)

            if match_pay:
                amt = float(match_pay.group(1))
                if amt > 0:
                    return ChatStructuredAction(
                        domain=ActionDomain.CREDIT,
                        action="payment",
                        customer_name=context.last_customer_name,
                        amount=amt
                    )

        # B. Credit purchase follow-up: "he took 500 on credit", "took 500 on credit"
        if getattr(context, "last_customer_name", None):
            match_cred = re.search(
                r"^(?:he|she|they)?\s*(?:took|borrowed)\s+[₹]?\s*([0-9]+(?:\.[0-9]+)?)\s*(?:on\s+credit|on\s+udhaar|udhaar|credit)$",
                clean
            )
            if match_cred:
                amt = float(match_cred.group(1))
                if amt > 0:
                    return ChatStructuredAction(
                        domain=ActionDomain.CREDIT,
                        action="credit_purchase",
                        customer_name=context.last_customer_name,
                        amount=amt
                    )

        # C. Credit item follow-up: "he took 2 on credit" with last_item_name & last_customer_name
        if getattr(context, "last_item_name", None):
            match_credit_item = re.search(
                r"^(?:he|she|they|[a-z\s]+?)?\s*(?:took|bought)\s+([0-9]+(?:\.[0-9]+)?)\s*(?:on\s+credit|on\s+udhaar|udhaar)$",
                clean
            )
            if match_credit_item:
                qty = float(match_credit_item.group(1))
                cust = getattr(context, "last_customer_name", None)
                if qty > 0 and cust:
                    return ChatStructuredAction(
                        domain=ActionDomain.CREDIT,
                        action="credit_purchase",
                        customer_name=cust,
                        item_name=context.last_item_name,
                        quantity=qty
                    )

        # D. Inventory operation follow-up: "sell 5", "sold 5", "damaged 2", "received 20" with last_item_name
        # Strictly matches ONLY if NO item is mentioned, only quantity + optional known unit!
        if getattr(context, "last_item_name", None):
            action_map = {
                "sold": "sold",
                "sell": "sold",
                "sale": "sold",
                "give": "sold",
                "received": "received",
                "receive": "received",
                "added": "received",
                "bought": "received",
                "damaged": "damaged",
                "damage": "damaged",
                "waste": "damaged",
                "returned": "returned",
                "return": "returned",
            }
            # Pattern 1: <action> <quantity> [allowed_unit]
            match_act_qty = re.search(
                rf"^(sold|sell|sale|give|received|receive|added|bought|damaged|damage|waste|returned|return)\s+([0-9]+(?:\.[0-9]+)?)(?:\s+({ALLOWED_UNITS}))?$",
                clean
            )
            if match_act_qty:
                act = action_map.get(match_act_qty.group(1), "sold")
                qty = float(match_act_qty.group(2))
                unit = match_act_qty.group(3)
                if qty > 0:
                    return ChatStructuredAction(
                        domain=ActionDomain.INVENTORY,
                        action=act,
                        item_name=context.last_item_name,
                        quantity=qty,
                        unit=unit
                    )

            # Pattern 2: <quantity> [allowed_unit] <action> (e.g. "5 sold", "2 damaged")
            match_qty_act = re.search(
                rf"^([0-9]+(?:\.[0-9]+)?)(?:\s+({ALLOWED_UNITS}))?\s+(sold|sell|received|damaged|returned)$",
                clean
            )
            if match_qty_act:
                qty = float(match_qty_act.group(1))
                unit = match_qty_act.group(2)
                act = action_map.get(match_qty_act.group(3), "sold")
                if qty > 0:
                    return ChatStructuredAction(
                        domain=ActionDomain.INVENTORY,
                        action=act,
                        item_name=context.last_item_name,
                        quantity=qty,
                        unit=unit
                    )

        return None

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
            if amount > 0 and customer and customer.lower() not in PRONOUNS:
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
            if amount > 0 and customer and customer.lower() not in PRONOUNS:
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
            if qty > 0 and customer and customer.lower() not in PRONOUNS and item:
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
            if amount > 0 and customer and not customer.isdigit() and customer.lower() not in PRONOUNS:
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
            if amount > 0 and customer and not customer.isdigit() and customer.lower() not in PRONOUNS:
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
            if amount > 0 and customer and not customer.isdigit() and customer.lower() not in PRONOUNS:
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
