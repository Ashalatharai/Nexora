from typing import List, Optional, Dict, Any
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
    CreditAction,
    CreditTransactionResponse
)
from app.schemas.summary import StockStatus
from app.services.inventory_service import InventoryService, format_qty
from app.services.credit_service import CreditService
from app.services.summary_service import SummaryService
from app.services.context_service import ContextManager
from app.parser import KiranaMessageParser
from app.parser.ai_parser import AIParser

router = APIRouter(prefix="/chat", tags=["Conversational Chat"])


@router.post("", response_model=ChatResponse, summary="Process chat message or pre-parsed actions")
def process_chat_message(request: ChatRequest, db: Session = Depends(get_db)):
    """
    Unified chat endpoint:
    - Session-aware conversational memory & context tracking.
    - Handles read-only queries (stock check, low-stock alerts, daily summary, customer balance, all udhaar, reorder draft) without DB mutations.
    - Contextual follow-ups (e.g. 'How much rice do I have?' -> 'Sell 5' -> Confirmation flow).
    - Pending action confirmation ('yes') and cancellation ('no').
    - Fallback to optional Gemini AI if configured, with strict deterministic parser baseline.
    - Accepts pre-parsed structured actions (from message-parser teammate).
    """
    session_id = request.session_id or "default"
    session = ContextManager.get_session(session_id)

    # 1. Check if user sent a pre-parsed structured action from message-parser module
    if request.actions and len(request.actions) > 0:
        actions = request.actions
        first_domain = actions[0].domain.value if hasattr(actions[0].domain, 'value') else str(actions[0].domain)
        intent = "inventory" if first_domain == "inventory" else "credit"
        return _execute_actions(actions, intent, request.message or "Direct actions", session_id, db)

    raw_msg = (request.message or "").strip()
    if not raw_msg:
        return ChatResponse(
            success=False,
            reply="Message was empty. Please type an inventory or credit update (e.g. 'sold 3 maggi', 'Ramesh paid 200').",
            intent="unrecognized",
            parsed_actions=[]
        )

    # Record message in conversation history
    ContextManager.add_history(session_id, "user", raw_msg)

    # 2. Check for Pending Confirmation / Cancellation
    clean_lower = raw_msg.lower().strip()
    if clean_lower in ["yes", "yep", "yeah", "confirm", "proceed", "haan", "sure", "correct", "do it", "ha", "ok", "okay"]:
        if session.pending_action:
            pending = ContextManager.clear_pending(session_id)
            return _execute_pending_action(pending, session_id, db)
        else:
            return ChatResponse(
                success=True,
                reply="There are no pending actions waiting for confirmation.",
                intent="confirmation"
            )

    if clean_lower in ["no", "nope", "cancel", "stop", "abort", "nah", "mat karo", "don't", "dont", "dont do it", "cancel that"]:
        if session.pending_action:
            ContextManager.clear_pending(session_id)
            return ChatResponse(
                success=True,
                reply="❌ Cancelled. No changes were made to your records.",
                intent="cancellation"
            )
        else:
            return ChatResponse(
                success=True,
                reply="Nothing to cancel.",
                intent="cancellation"
            )

    # 3. Parse message with conversation session context
    parse_res = KiranaMessageParser.parse(raw_msg, context=session)

    # 4. Handle Read-Only Queries (Zero database writes)
    if parse_res.intent == "query" and parse_res.actions:
        query_action = parse_res.actions[0]
        return _handle_query(query_action, session_id, db)

    # 5. Handle Contextual Follow-Up with confirmation state machine
    if parse_res.intent == "followup_confirmation" and parse_res.actions:
        action = parse_res.actions[0]
        action_dict = action.model_dump() if hasattr(action, 'model_dump') else action.dict()

        if action.domain == ActionDomain.INVENTORY:
            confirm_prompt = (
                f"Do you want to record {action.action} of {format_qty(action.quantity)} "
                f"{action.item_name.title()}{(' ' + action.unit) if action.unit else ''}? "
                f"(Reply 'yes' to confirm or 'no' to cancel)"
            )
        elif action.action == "payment":
            confirm_prompt = (
                f"Do you want to record a payment of ₹{action.amount:g} from {action.customer_name}? "
                f"(Reply 'yes' to confirm or 'no' to cancel)"
            )
        elif action.item_name:
            confirm_prompt = (
                f"Do you want to record {action.customer_name} taking {format_qty(action.quantity)} "
                f"{action.item_name.title()} on credit? (Reply 'yes' to confirm or 'no' to cancel)"
            )
        else:
            confirm_prompt = (
                f"Do you want to record ₹{action.amount:g} credit for {action.customer_name}? "
                f"(Reply 'yes' to confirm or 'no' to cancel)"
            )

        ContextManager.set_pending(session_id, action_dict, confirm_prompt)
        ContextManager.add_history(session_id, "assistant", confirm_prompt)

        return ChatResponse(
            success=True,
            reply=confirm_prompt,
            intent="confirmation_pending",
            pending_action=action_dict
        )

    # 6. Handle Ambiguity / Incomplete messages
    if not parse_res.success:
        # Check optional Gemini fallback if available
        if AIParser.is_available():
            ai_action = AIParser.parse_with_gemini(raw_msg, session)
            if ai_action:
                action_dict = ai_action.model_dump() if hasattr(ai_action, 'model_dump') else ai_action.dict()
                confirm_prompt = f"I understood you want to: {ai_action.action} {ai_action.item_name or ai_action.customer_name}. Reply 'yes' to confirm or 'no' to cancel."
                ContextManager.set_pending(session_id, action_dict, confirm_prompt)
                return ChatResponse(
                    success=True,
                    reply=confirm_prompt,
                    intent="confirmation_pending",
                    pending_action=action_dict
                )

        # Return clear guidance
        reply_msg = parse_res.clarification_prompt or "I couldn't understand that command."
        ContextManager.add_history(session_id, "assistant", reply_msg)
        return ChatResponse(
            success=False,
            reply=reply_msg,
            intent=parse_res.intent,
            parsed_actions=[]
        )

    # 7. Standard Mutation Execution (inventory or credit updates)
    return _execute_actions(parse_res.actions, parse_res.intent, raw_msg, session_id, db)


def _handle_query(query_action: ChatStructuredAction, session_id: str, db: Session) -> ChatResponse:
    """Execute read-only queries with zero database mutations."""
    q_type = query_action.action

    if q_type == "stock_item":
        item_name = query_action.item_name
        item = InventoryService.get_item_by_name(db, item_name)
        if item:
            ContextManager.set_last_item(session_id, item.name)
            reply = f"📦 {item.name.title()}: You currently have {format_qty(item.quantity)} {item.unit} in stock (@ ₹{item.price:g}/{item.unit})."
            if item.is_out_of_stock:
                reply += " 🚨 Completely OUT OF STOCK!"
            elif item.is_low_stock:
                reply += f" ⚠️ Low stock alert (threshold: {item.min_threshold:g} {item.unit})!"
            ContextManager.add_history(session_id, "assistant", reply)
            return ChatResponse(success=True, reply=reply, intent="query")
        else:
            reply = f"Item '{item_name}' was not found in inventory."
            ContextManager.add_history(session_id, "assistant", reply)
            return ChatResponse(success=False, reply=reply, intent="query")

    elif q_type == "low_stock":
        items = SummaryService.get_low_stock_items(db)
        if not items:
            reply = "✅ All inventory items are adequately stocked! No low-stock alerts right now."
        else:
            lines = [f"⚠️ Low Stock Alerts ({len(items)} items):"]
            for it in items:
                urgency = "🚨 OUT OF STOCK" if it.status == StockStatus.OUT_OF_STOCK else "⚠️ Low Stock"
                lines.append(f"• {it.name}: {format_qty(it.current_stock)} {it.unit} left (Min: {format_qty(it.min_threshold)} {it.unit}) — {urgency}")
            reply = "\n".join(lines)
        ContextManager.add_history(session_id, "assistant", reply)
        return ChatResponse(success=True, reply=reply, intent="query")

    elif q_type == "daily_summary":
        summary = SummaryService.get_daily_summary(db)
        reply = (
            f"📊 Today's Summary ({summary.date}):\n"
            f"• Gross Sales: ₹{summary.gross_sales_value_inr:g}\n"
            f"• Total Inventory Actions: {summary.total_inventory_actions}\n"
            f"• Credit Collected: ₹{summary.credit_summary.total_payments_received_amount:g}\n"
            f"• New Udhaar Given: ₹{summary.credit_summary.total_credit_purchases_amount:g}\n"
            f"ℹ️ {summary.accounting_note}"
        )
        ContextManager.add_history(session_id, "assistant", reply)
        return ChatResponse(success=True, reply=reply, intent="query")

    elif q_type == "customer_balance":
        cust_name = query_action.customer_name
        customer = CreditService.get_customer_by_name(db, cust_name)
        ContextManager.set_last_customer(session_id, cust_name)
        if customer:
            reply = f"👤 {customer.name}: Current outstanding balance is ₹{customer.outstanding_balance:g}."
            if customer.outstanding_balance == 0:
                reply += " (No pending debt)"
        else:
            reply = f"👤 {cust_name}: No credit record found (balance is ₹0)."
        ContextManager.add_history(session_id, "assistant", reply)
        return ChatResponse(success=True, reply=reply, intent="query")

    elif q_type == "all_udhaar":
        customers = CreditService.list_customers(db)
        owing = [c for c in customers if c.outstanding_balance > 0]
        if not owing:
            reply = "🎉 No outstanding Udhaar! All customers have clear balances."
        else:
            total_debt = sum(c.outstanding_balance for c in owing)
            lines = [f"📋 Outstanding Udhaar ({len(owing)} customers, Total: ₹{total_debt:g}):"]
            for c in owing:
                lines.append(f"• {c.name}: ₹{c.outstanding_balance:g}")
            reply = "\n".join(lines)
        ContextManager.add_history(session_id, "assistant", reply)
        return ChatResponse(success=True, reply=reply, intent="query")

    elif q_type == "reorder_draft":
        reorder = SummaryService.generate_supplier_reorder(db)
        reply = f"📝 Supplier Reorder Draft:\n\n{reorder.message_text}\n\n🔗 WhatsApp Link: {reorder.whatsapp_url}"
        ContextManager.add_history(session_id, "assistant", reply)
        return ChatResponse(success=True, reply=reply, intent="query")

    return ChatResponse(success=False, reply="Query not recognized.", intent="query")


def _execute_pending_action(pending: Dict[str, Any], session_id: str, db: Session) -> ChatResponse:
    """Execute confirmed pending action atomically."""
    domain = pending.get("domain", "inventory")
    action_name = pending.get("action", "sold")

    if domain == "inventory" or domain == ActionDomain.INVENTORY:
        item_name = pending["item_name"]
        quantity = pending["quantity"]
        raw_act = action_name.lower()
        if raw_act in ["sold", "sell"]:
            enum_act = InventoryAction.SOLD
        elif raw_act in ["received", "receive", "added"]:
            enum_act = InventoryAction.RECEIVED
        elif raw_act in ["damaged", "damage"]:
            enum_act = InventoryAction.DAMAGED
        elif raw_act in ["returned", "return"]:
            enum_act = InventoryAction.RETURNED
        else:
            enum_act = InventoryAction.SOLD

        inv_req = InventoryTransactionRequest(
            items=[SingleItemAction(action=enum_act, item_name=item_name, quantity=quantity)],
            note="Confirmed via chat"
        )
        inv_res = InventoryService.execute_transaction(db, inv_req)
        reply_text = f"✅ Confirmed! {inv_res.confirmation}"
        if inv_res.low_stock_alerts:
            reply_text += "\n" + "\n".join(inv_res.low_stock_alerts)

        ContextManager.set_last_item(session_id, item_name)
        ContextManager.add_history(session_id, "assistant", reply_text)

        return ChatResponse(
            success=True,
            reply=reply_text,
            intent="inventory",
            inventory_updates=inv_res.updates,
            low_stock_alerts=inv_res.low_stock_alerts
        )

    elif domain == "credit" or domain == ActionDomain.CREDIT:
        customer_name = pending["customer_name"]
        # Case 1: Credit purchase of item
        if pending.get("item_name") and pending.get("quantity"):
            item_name = pending["item_name"]
            qty = pending["quantity"]
            item = InventoryService.get_item_by_name(db, item_name)
            if not item:
                raise HTTPException(status_code=400, detail=f"Item '{item_name}' was not found.")
            if item.quantity < qty:
                raise HTTPException(status_code=400, detail=f"Insufficient stock for '{item.name.title()}'.")

            amt = pending.get("amount") or round(qty * item.price, 2)
            inv_res = InventoryService.execute_transaction(
                db,
                InventoryTransactionRequest(
                    items=[SingleItemAction(action=InventoryAction.SOLD, item_name=item.name, quantity=qty)],
                    note=f"Confirmed credit sale to {customer_name}"
                )
            )
            credit_req = CreditTransactionRequest(
                customer_name=customer_name,
                action=CreditAction.CREDIT_PURCHASE,
                amount=amt,
                details=f"{format_qty(qty)} {item.name.title()} @ ₹{item.price:g}"
            )
            credit_res = CreditService.execute_credit_transaction(db, credit_req)
            reply = f"✅ Confirmed! {inv_res.confirmation}. {credit_res.confirmation}"
            if inv_res.low_stock_alerts:
                reply += "\n" + "\n".join(inv_res.low_stock_alerts)

            ContextManager.set_last_item(session_id, item.name)
            ContextManager.set_last_customer(session_id, customer_name)
            ContextManager.add_history(session_id, "assistant", reply)

            return ChatResponse(
                success=True,
                reply=reply,
                intent="credit",
                inventory_updates=inv_res.updates,
                credit_update=credit_res,
                low_stock_alerts=inv_res.low_stock_alerts
            )

        # Case 2: Credit payment or direct credit
        if action_name in ["payment", "paid", "clear"]:
            mapped_action = CreditAction.PAYMENT
        else:
            mapped_action = CreditAction.CREDIT_PURCHASE

        credit_req = CreditTransactionRequest(
            customer_name=customer_name,
            action=mapped_action,
            amount=pending["amount"],
            details="Confirmed via chat"
        )
        res = CreditService.execute_credit_transaction(db, credit_req)
        reply = f"✅ Confirmed! {res.confirmation}"
        ContextManager.set_last_customer(session_id, customer_name)
        ContextManager.add_history(session_id, "assistant", reply)

        return ChatResponse(
            success=True,
            reply=reply,
            intent="credit",
            credit_update=res
        )

    return ChatResponse(success=False, reply="Could not execute pending action.", intent="unknown")


def _execute_actions(
    actions: List[ChatStructuredAction],
    intent: str,
    original_message: str,
    session_id: str,
    db: Session
) -> ChatResponse:
    """Execute parsed actions (credit or inventory) with database mutations."""
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

            calculated_amount = credit_act.amount if credit_act.amount is not None else round(qty * item.price, 2)

            inv_res = InventoryService.execute_transaction(
                db,
                InventoryTransactionRequest(
                    items=[SingleItemAction(action=InventoryAction.SOLD, item_name=item.name, quantity=qty)],
                    note=f"Credit sale to {credit_act.customer_name}"
                )
            )

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

            ContextManager.set_last_item(session_id, item.name)
            ContextManager.set_last_customer(session_id, credit_act.customer_name)
            ContextManager.add_history(session_id, "assistant", combined_reply)

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
            details=f"Via chat: {original_message}"
        )

        res = CreditService.execute_credit_transaction(db, credit_req)

        ContextManager.set_last_customer(session_id, credit_act.customer_name)
        ContextManager.add_history(session_id, "assistant", res.confirmation)

        return ChatResponse(
            success=True,
            reply=res.confirmation,
            intent="credit",
            parsed_actions=actions,
            credit_update=res
        )

    # Inventory Domain
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
        note=f"Via chat: {original_message}"
    )

    inv_res = InventoryService.execute_transaction(db, inv_req)

    reply_text = inv_res.confirmation
    if inv_res.low_stock_alerts:
        reply_text += "\n" + "\n".join(inv_res.low_stock_alerts)

    ContextManager.set_last_item(session_id, inv_items[0].item_name)
    ContextManager.add_history(session_id, "assistant", reply_text)

    return ChatResponse(
        success=True,
        reply=reply_text,
        intent="inventory",
        parsed_actions=actions,
        inventory_updates=inv_res.updates,
        low_stock_alerts=inv_res.low_stock_alerts
    )
