from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.chat import (
    ChatRequest,
    ChatResponse,
    ChatStructuredAction,
    ActionDomain
)
from app.schemas.inventory import (
    SingleItemAction,
    InventoryAction,
    InventoryTransactionRequest
)
from app.schemas.credit import (
    CreditTransactionRequest,
    CreditAction
)
from app.services.inventory_service import InventoryService
from app.services.credit_service import CreditService
from app.services.parser_service import MessageParserFallback

router = APIRouter(prefix="/chat", tags=["Conversational Chat"])


@router.post("", response_model=ChatResponse, summary="Process chat message or pre-parsed actions")
def process_chat_message(request: ChatRequest, db: Session = Depends(get_db)):
    """
    Unified chat endpoint:
    - Accepts pre-parsed structured actions (from the message-parser teammate).
    - Falls back to rule-based parsing if raw text is sent without actions.
    - Returns a clear human-readable confirmation suitable for chat UI.
    """
    actions: List[ChatStructuredAction] = []
    intent = "unknown"

    # 1. Check if structured actions were passed from message-parser
    if request.actions and len(request.actions) > 0:
        actions = request.actions
        first_domain = actions[0].domain.value if hasattr(actions[0].domain, 'value') else str(actions[0].domain)
        intent = "inventory" if first_domain == "inventory" else "credit"
    elif request.message:
        # 2. Fall back to internal decoupled message parser
        actions, intent = MessageParserFallback.parse_message(request.message)

    if not actions:
        return ChatResponse(
            success=False,
            reply=(
                "I couldn't understand that command. Try typing:\n"
                "• 'sold 3 maggi, 2 milk'\n"
                "• 'received 20 rice bags'\n"
                "• 'damaged 1 oil'\n"
                "• 'Ramesh paid ₹200'\n"
                "• 'Ramesh took 500 on credit'"
            ),
            intent="unrecognized",
            parsed_actions=[]
        )

    # 3. Route according to domain
    if intent == "credit":
        credit_act = actions[0]
        action_name = credit_act.action.lower()

        # Map to CreditAction enum
        if action_name in ["payment", "paid", "clear"]:
            mapped_action = CreditAction.PAYMENT
        else:
            mapped_action = CreditAction.CREDIT_PURCHASE

        if not credit_act.customer_name or credit_act.amount is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Credit actions must specify both customer_name and amount."
            )

        credit_req = CreditTransactionRequest(
            customer_name=credit_act.customer_name,
            action=mapped_action,
            amount=credit_act.amount,
            details=f"Via chat: {request.message or 'direct action'}"
        )

        res = CreditService.execute_credit_transaction(db, credit_req)

        return ChatResponse(
            success=True,
            reply=res.confirmation,
            intent="credit",
            parsed_actions=actions,
            credit_update=res
        )

    # 4. Inventory Domain
    inv_items: List[SingleItemAction] = []
    for act in actions:
        if not act.item_name or act.quantity is None:
            continue

        raw_act = act.action.lower()
        if raw_act in ["sold", "sell", "sale"]:
            enum_act = InventoryAction.SOLD
        elif raw_act in ["received", "receive", "bought", "purchased"]:
            enum_act = InventoryAction.RECEIVED
        elif raw_act in ["damaged", "damage", "waste"]:
            enum_act = InventoryAction.DAMAGED
        elif raw_act in ["returned", "return"]:
            enum_act = InventoryAction.RETURNED
        else:
            enum_act = InventoryAction.SOLD

        inv_items.append(
            SingleItemAction(
                action=enum_act,
                item_name=act.item_name,
                quantity=act.quantity
            )
        )

    if not inv_items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No valid items found in the message to update."
        )

    inv_req = InventoryTransactionRequest(
        items=inv_items,
        note=f"Via chat: {request.message or 'direct action'}"
    )

    inv_res = InventoryService.execute_transaction(db, inv_req)

    reply_text = inv_res.confirmation
    if inv_res.low_stock_alerts:
        reply_text += "\n" + "\n".join(inv_res.low_stock_alerts)

    return ChatResponse(
        success=True,
        reply=reply_text,
        intent="inventory",
        parsed_actions=actions,
        inventory_updates=inv_res.updates,
        low_stock_alerts=inv_res.low_stock_alerts
    )
