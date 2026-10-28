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
    InventoryTransactionRequest,
    ItemUpdateResult
)
from app.schemas.credit import (
    CreditTransactionRequest,
    CreditAction
)
from app.services.inventory_service import InventoryService, format_qty
from app.services.credit_service import CreditService
from app.parser import KiranaMessageParser

router = APIRouter(prefix="/chat", tags=["Conversational Chat"])


@router.post("", response_model=ChatResponse, summary="Process chat message or pre-parsed actions")
def process_chat_message(request: ChatRequest, db: Session = Depends(get_db)):
    """
    Unified chat endpoint:
    - Accepts pre-parsed structured actions (from the message-parser teammate).
    - Falls back to rule-based parsing if raw text is sent without actions.
    - Supports atomic combined credit-item purchases (e.g. 'Ramesh took 2 rice on credit').
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
        parse_res = KiranaMessageParser.parse(request.message)
        if not parse_res.success:
            return ChatResponse(
                success=False,
                reply=parse_res.clarification_prompt or "I couldn't understand that command.",
                intent=parse_res.intent,
                parsed_actions=[]
            )
        actions = parse_res.actions
        intent = parse_res.intent

    if not actions:
        return ChatResponse(
            success=False,
            reply=(
                "I couldn't understand that command. Try typing:\n"
                "• 'sold 3 maggi, 2 milk'\n"
                "• 'received 20 rice bags'\n"
                "• 'damaged 1 oil'\n"
                "• 'Ramesh took 2 rice on credit'\n"
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

        if action_name in ["payment", "paid", "clear"]:
            mapped_action = CreditAction.PAYMENT
        else:
            mapped_action = CreditAction.CREDIT_PURCHASE

        if not credit_act.customer_name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Credit actions must specify customer_name."
            )

        # Special Case: Credit sale of an inventory item (e.g. 'Ramesh took 2 rice on credit')
        if credit_act.item_name and credit_act.quantity:
            item = InventoryService.get_item_by_name(db, credit_act.item_name)
            if not item:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Item '{credit_act.item_name}' was not found in inventory."
                )

            qty = credit_act.quantity
            if item.quantity < qty:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"Insufficient stock for '{item.name.title()}'. "
                        f"Only {format_qty(item.quantity)} {item.unit} available, but {format_qty(qty)} requested on credit."
                    )
                )

            # Calculate price
            calculated_amount = credit_act.amount if credit_act.amount is not None else round(qty * item.price, 2)

            # Deduct stock atomically
            inv_res = InventoryService.execute_transaction(
                db,
                InventoryTransactionRequest(
                    items=[SingleItemAction(action=InventoryAction.SOLD, item_name=item.name, quantity=qty)],
                    note=f"Credit sale to {credit_act.customer_name}"
                )
            )

            # Add to customer Udhaar
            credit_req = CreditTransactionRequest(
                customer_name=credit_act.customer_name,
                action=CreditAction.CREDIT_PURCHASE,
                amount=calculated_amount,
                details=f"{format_qty(qty)} {item.name.title()} @ ₹{item.price:g}/{item.unit}"
            )
            credit_res = CreditService.execute_credit_transaction(db, credit_req)

            combined_reply = (
                f"{inv_res.confirmation}. "
                f"{credit_res.confirmation} ({format_qty(qty)} {item.name.title()} @ ₹{item.price:g} = ₹{calculated_amount:g})"
            )
            if inv_res.low_stock_alerts:
                combined_reply += "\n" + "\n".join(inv_res.low_stock_alerts)

            return ChatResponse(
                success=True,
                reply=combined_reply,
                intent="credit",
                parsed_actions=actions,
                inventory_updates=inv_res.updates,
                credit_update=credit_res,
                low_stock_alerts=inv_res.low_stock_alerts
            )

        # Standard Credit Amount Transaction
        if credit_act.amount is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Credit transaction must specify an amount."
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
        elif raw_act in ["received", "receive", "bought", "purchased", "added"]:
            enum_act = InventoryAction.RECEIVED
        elif raw_act in ["damaged", "damage", "waste", "expired", "broken"]:
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
