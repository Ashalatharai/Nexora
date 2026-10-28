from typing import List, Tuple, Optional, Any
from app.parser.schemas import ParseResult, AmbiguityType
from app.parser.normalizer import TextNormalizer
from app.parser.ambiguity import AmbiguityDetector
from app.parser.intents import IntentParser
from app.schemas.chat import ChatStructuredAction


class KiranaMessageParser:
    """
    Production-grade, deterministic natural-language message parser for Kirana Chat Ledger.
    Executes in isolated phases:
    1. Input Normalization
    2. Read-Only Query & Confirmation Detection
    3. Standalone Ambiguity & Incomplete Input Detection
    4. Intent Detection & Entity Extraction (Direct Transactions)
    5. Contextual Follow-Up Intent Resolution
    6. Context-Aware Ambiguity Validation
    7. Structured Contract Assembly
    """

    @classmethod
    def parse(cls, raw_text: str, context: Any = None) -> ParseResult:
        if not raw_text or not raw_text.strip():
            return ParseResult(
                raw_message=raw_text or "",
                clean_message="",
                intent="unrecognized",
                success=False,
                is_ambiguous=True,
                ambiguity_type=AmbiguityType.UNRECOGNIZED,
                clarification_prompt="Message was empty. Please type an inventory or credit update (e.g. 'sold 3 maggi', 'Ramesh paid 200')."
            )

        # Phase 1: Input Normalization
        clean = TextNormalizer.normalize(raw_text)

        # Phase 2: Read-Only Query & Confirmation Detection (Queries take precedence over ambiguity)
        query_act = IntentParser.parse_query(clean)
        if query_act:
            if query_act.action == "confirm":
                return ParseResult(
                    raw_message=raw_text,
                    clean_message=clean,
                    intent="confirmation",
                    success=True,
                    actions=[query_act]
                )
            elif query_act.action == "cancel":
                return ParseResult(
                    raw_message=raw_text,
                    clean_message=clean,
                    intent="cancellation",
                    success=True,
                    actions=[query_act]
                )
            else:
                return ParseResult(
                    raw_message=raw_text,
                    clean_message=clean,
                    intent="query",
                    success=True,
                    actions=[query_act]
                )

        # Phase 3: Standalone Ambiguity Detection (e.g. negative numbers, 'sold some rice', 'add stock', '3 maggi')
        # Note: Do not reject action+quantity here yet if context might resolve it
        is_ambiguous, amb_type, clarification_msg = AmbiguityDetector.check_ambiguity(clean, context=context)
        if is_ambiguous and amb_type not in [AmbiguityType.MISSING_ITEM, AmbiguityType.MISSING_CUSTOMER]:
            return ParseResult(
                raw_message=raw_text,
                clean_message=clean,
                intent="ambiguous",
                success=False,
                is_ambiguous=True,
                ambiguity_type=amb_type,
                clarification_prompt=clarification_msg
            )

        # Phase 4: Intent Detection & Entity Extraction (Standard Transactions)
        # Priority 1: Customer Credit Payment (e.g. "Ramesh paid 200", "received 500 from Ramesh")
        credit_payment = IntentParser.parse_credit_payment(clean)
        if credit_payment:
            return ParseResult(
                raw_message=raw_text,
                clean_message=clean,
                intent="credit",
                success=True,
                actions=[credit_payment]
            )

        # Priority 2: Customer Credit Purchase of Items (e.g. "Ramesh took 2 rice on credit", "give Ramesh 3 soaps on udhaar")
        credit_item = IntentParser.parse_credit_item_purchase(clean)
        if credit_item:
            return ParseResult(
                raw_message=raw_text,
                clean_message=clean,
                intent="credit",
                success=True,
                actions=[credit_item]
            )

        # Priority 3: Customer Direct Credit Amount (e.g. "Ramesh took 500 on credit", "udhaar Ramesh 300")
        credit_amount = IntentParser.parse_credit_direct_amount(clean)
        if credit_amount:
            return ParseResult(
                raw_message=raw_text,
                clean_message=clean,
                intent="credit",
                success=True,
                actions=[credit_amount]
            )

        # Priority 4: Inventory Operations (Single or Multiple Items: sales, receipts, damages, returns)
        inv_actions = IntentParser.parse_inventory_clauses(clean)
        if inv_actions:
            return ParseResult(
                raw_message=raw_text,
                clean_message=clean,
                intent="inventory",
                success=True,
                actions=inv_actions
            )

        # Phase 5: Contextual Follow-Up Intent Resolution (e.g. "sell 5" when context has "rice")
        if context:
            followup_act = IntentParser.parse_contextual_followup(clean, context)
            if followup_act:
                return ParseResult(
                    raw_message=raw_text,
                    clean_message=clean,
                    intent="followup_confirmation",
                    success=True,
                    actions=[followup_act]
                )

        # Phase 6: If an ambiguity was detected earlier for missing item/customer without context
        if is_ambiguous:
            return ParseResult(
                raw_message=raw_text,
                clean_message=clean,
                intent="ambiguous",
                success=False,
                is_ambiguous=True,
                ambiguity_type=amb_type,
                clarification_prompt=clarification_msg
            )

        # Fallback: Unrecognized
        return ParseResult(
            raw_message=raw_text,
            clean_message=clean,
            intent="unrecognized",
            success=False,
            is_ambiguous=True,
            ambiguity_type=AmbiguityType.UNRECOGNIZED,
            clarification_prompt=(
                "I couldn't understand that command. Try typing:\n"
                "• 'sold 3 maggi, 2 milk'\n"
                "• 'received 20 rice bags'\n"
                "• 'damaged 2 oil bottles'\n"
                "• 'customer returned 2 soaps'\n"
                "• 'Ramesh took 2 rice on credit'\n"
                "• 'Ramesh paid 200'\n"
                "• 'How much rice do I have?'\n"
                "• 'How much does Ramesh owe?'"
            )
        )
