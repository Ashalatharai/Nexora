import json
import re
from datetime import datetime
from typing import List, Dict, Any, Tuple, Optional
import httpx

from config import settings
from database import get_db_connection, db_transaction, dict_from_row
from parser import RuleParser, match_product, match_customer, extract_candidate_product

WORD_NUMBERS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "twenty": 20, "thirty": 30, "fifty": 50, "hundred": 100
}

class ChatEngine:
    @staticmethod
    def get_store_context(conn) -> Dict[str, Any]:
        """Fetch ground-truth database snapshot for real business context."""
        cursor = conn.cursor()

        # 1. Products
        cursor.execute("SELECT id, name, category, price, cost_price, stock, min_stock, unit FROM products ORDER BY name ASC")
        products = [dict_from_row(r) for r in cursor.fetchall()]

        # 2. Customers
        cursor.execute("SELECT id, name, phone, due FROM customers ORDER BY due DESC")
        customers = [dict_from_row(r) for r in cursor.fetchall()]

        # 3. Today's Transactions
        cursor.execute("""
            SELECT type, SUM(amount) as total_amount, SUM(profit) as total_profit, COUNT(*) as count 
            FROM transactions 
            WHERE date = 'Today' 
            GROUP BY type
        """)
        today_metrics = {r["type"]: dict_from_row(r) for r in cursor.fetchall()}

        sales_today = today_metrics.get("sale", {}).get("total_amount", 0.0) or 0.0
        profit_today = today_metrics.get("sale", {}).get("total_profit", 0.0) or 0.0
        credit_today = today_metrics.get("credit", {}).get("total_amount", 0.0) or 0.0
        payments_today = today_metrics.get("payment", {}).get("total_amount", 0.0) or 0.0

        # 4. Total Udhaar
        cursor.execute("SELECT COALESCE(SUM(due), 0.0) as total_due FROM customers")
        total_due = cursor.fetchone()["total_due"]

        # 5. Low stock products
        low_stock = [p for p in products if p["stock"] <= p["min_stock"]]

        # 6. Recent transactions
        cursor.execute("SELECT title, detail, amount, type, time FROM transactions ORDER BY created_at DESC LIMIT 5")
        recent_txs = [dict_from_row(r) for r in cursor.fetchall()]

        return {
            "products": products,
            "customers": customers,
            "metrics": {
                "sales_today": round(sales_today, 2),
                "profit_today": round(profit_today, 2),
                "credit_today": round(credit_today, 2),
                "payments_today": round(payments_today, 2),
                "total_outstanding_udhaar": round(total_due, 2),
                "low_stock_count": len(low_stock)
            },
            "low_stock_items": [f"{p['name']} ({p['stock']} {p['unit']} left, alert at {p['min_stock']})" for p in low_stock],
            "recent_transactions": recent_txs
        }

    @staticmethod
    def get_session_history(conn, session_id: str, limit: int = 6) -> List[Dict[str, str]]:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT role, text FROM chat_history WHERE session_id = ? ORDER BY id DESC LIMIT ?",
            (session_id, limit)
        )
        rows = cursor.fetchall()
        return [{"role": r["role"], "text": r["text"]} for r in reversed(rows)]

    @staticmethod
    def save_message(conn, session_id: str, role: str, text: str, action: str = None):
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO chat_history (session_id, role, text, action_taken) VALUES (?, ?, ?, ?)",
            (session_id, role, text, action)
        )
        conn.commit()

    @classmethod
    async def process_chat(cls, user_message: str, session_id: str = "default") -> Dict[str, Any]:
        """Main chat orchestrator combining LLM understanding with rule-based safety."""
        raw = user_message.strip()
        if not raw:
            return {
                "reply": "Please type a message or ask me a question about your shop.",
                "action_taken": "none",
                "clarification_needed": True
            }

        conn = get_db_connection()
        context = cls.get_store_context(conn)
        history = cls.get_session_history(conn, session_id)

        # 1. Attempt LLM-based intent parsing & answer generation if API key is provided
        api_key = settings.GEMINI_API_KEY or settings.OPENAI_API_KEY
        if api_key:
            try:
                result = await cls._process_with_llm(raw, history, context)
                if result:
                    cls.save_message(conn, session_id, "user", raw)
                    cls.save_message(conn, session_id, "assistant", result["reply"], result.get("action_taken"))
                    conn.close()
                    return result
            except Exception as e:
                print(f"[LLM Engine Warning]: {e}. Falling back to deterministic engine.")

        # 2. Intelligent local engine (live DB queries + fuzzy rule parser)
        result = cls._process_local(raw, history, context)
        cls.save_message(conn, session_id, "user", raw)
        cls.save_message(conn, session_id, "assistant", result["reply"], result.get("action_taken"))
        conn.close()
        return result

    @classmethod
    async def _process_with_llm(cls, user_message: str, history: List[Dict[str, str]], context: Dict[str, Any]) -> Dict[str, Any]:
        """Calls Google Gemini API or OpenAI API with ground-truth SQLite data."""
        if settings.GEMINI_API_KEY:
            return await cls._call_gemini(user_message, history, context)
        elif settings.OPENAI_API_KEY:
            return await cls._call_openai(user_message, history, context)
        return None

    @classmethod
    async def _call_gemini(cls, user_message: str, history: List[Dict[str, str]], context: Dict[str, Any]) -> Dict[str, Any]:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{settings.GEMINI_MODEL}:generateContent?key={settings.GEMINI_API_KEY}"
        system_instruction = cls._build_system_prompt(context)

        contents = []
        for h in history:
            role = "user" if h["role"] == "user" else "model"
            contents.append({"role": role, "parts": [{"text": h["text"]}]})

        contents.append({"role": "user", "parts": [{"text": user_message}]})

        payload = {
            "system_instruction": {"parts": [{"text": system_instruction}]},
            "contents": contents,
            "generationConfig": {
                "temperature": 0.1,
                "response_mime_type": "application/json"
            }
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            res = await client.post(url, json=payload)
            if res.status_code != 200:
                raise RuntimeError(f"Gemini API returned status {res.status_code}: {res.text}")

            data = res.json()
            raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
            parsed = json.loads(raw_text)

            return cls._handle_llm_action_and_response(parsed, user_message)

    @classmethod
    async def _call_openai(cls, user_message: str, history: List[Dict[str, str]], context: Dict[str, Any]) -> Dict[str, Any]:
        url = "https://api.openai.com/v1/chat/completions"
        system_instruction = cls._build_system_prompt(context)

        messages = [{"role": "system", "content": system_instruction}]
        for h in history:
            messages.append({"role": h["role"], "content": h["text"]})
        messages.append({"role": "user", "content": user_message})

        payload = {
            "model": "gpt-4o-mini",
            "messages": messages,
            "temperature": 0.1,
            "response_format": {"type": "json_object"}
        }

        headers = {
            "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
            "Content-Type": "application/json"
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            res = await client.post(url, json=payload, headers=headers)
            if res.status_code != 200:
                raise RuntimeError(f"OpenAI API returned status {res.status_code}: {res.text}")

            data = res.json()
            raw_text = data["choices"][0]["message"]["content"]
            parsed = json.loads(raw_text)

            return cls._handle_llm_action_and_response(parsed, user_message)

    @classmethod
    def _build_system_prompt(cls, context: Dict[str, Any]) -> str:
        return f"""
You are the AI Assistant for Kirana Chat Ledger, a practical shopkeeper assistant for an Indian kirana store.
Shop name: Sharma General Store.

You must respond in JSON with the exact structure:
{{
  "intent": "SALE" | "RESTOCK" | "CREDIT" | "PAYMENT" | "CREATE_CUSTOMER" | "QUERY" | "CLARIFICATION" | "GENERAL",
  "action_params": {{
    "product_name": string or null,
    "quantity": integer or null,
    "customer_name": string or null,
    "phone": string or null,
    "amount": float or null
  }},
  "reply": string
}}

CURRENT LIVE SHOP DATA (SQLite ground truth):
- Products in stock: {json.dumps(context['products'])}
- Customers & Udhaar balances: {json.dumps(context['customers'])}
- Today's Business Metrics: {json.dumps(context['metrics'])}
- Low stock items: {json.dumps(context['low_stock_items'])}
- Recent transactions: {json.dumps(context['recent_transactions'])}

CRITICAL TRANSACTION RULES:
1. When a user requests a sale or a customer purchases a product (e.g. "Deeksha bought 2 maggie", "Sold 2 Maggi to Deeksha"):
   - Set intent="SALE". action_params must have product_name, quantity, and customer_name if specified.
2. When a customer takes items on credit (e.g. "Deeksha took 2 Maggi on credit"):
   - Set intent="CREDIT".
3. When stock is added (e.g. "Add 10 Maggi packets to stock"):
   - Set intent="RESTOCK".
4. When a customer pays money (e.g. "Deeksha paid 100"):
   - Set intent="PAYMENT". action_params must have customer_name and amount.
5. When a new customer is registered (e.g. "Add new customer Ramesh"):
   - Set intent="CREATE_CUSTOMER". action_params must have customer_name and optional phone.
6. If the transaction direction is ambiguous (e.g. "Deeksha took 2 Maggi" without specifying cash or credit):
   - Set intent="CLARIFICATION", ask: "Did Deeksha pay cash or take 2 Maggi on credit?"
7. Never fabricate numbers. Live execution and stock validation will be enforced by the backend RuleParser.
"""

    @classmethod
    def _handle_llm_action_and_response(cls, parsed: Dict[str, Any], raw_query: str) -> Dict[str, Any]:
        """Validates and executes database write actions identified by LLM."""
        intent = (parsed.get("intent") or "GENERAL").upper()
        params = parsed.get("action_params") or {}
        llm_reply = parsed.get("reply", "")

        # 1. SALE
        if intent == "SALE" and params.get("product_name"):
            res = RuleParser.execute_sale(
                product_query=params["product_name"],
                quantity=params.get("quantity") or 1,
                raw_query=raw_query,
                customer_query=params.get("customer_name")
            )
            if res["success"]:
                cust_info = f" to {res['customer_name']}" if res.get("customer_name") else ""
                reply = f"Recorded sale of {res['quantity']} {res['unit']}(s) of {res['product_name']}{cust_info} (₹{res['total_amount']:0.2f}). Remaining stock: {res['remaining_stock']}."
                if res.get("warning"):
                    reply += f" ⚠️ {res['warning']}"
                return {"reply": reply, "action_taken": "sale", "action_details": res, "clarification_needed": False}
            else:
                return {"reply": res["error"], "action_taken": "none", "clarification_needed": res.get("clarification_needed", False)}

        # 2. RESTOCK
        if intent == "RESTOCK" and params.get("product_name"):
            res = RuleParser.execute_restock(
                product_query=params["product_name"],
                quantity=params.get("quantity") or 1,
                raw_query=raw_query
            )
            if res["success"]:
                reply = f"Stock updated! Added {res['quantity_added']} {res['unit']}(s) to {res['product_name']}. New inventory count: {res['new_stock']}."
                return {"reply": reply, "action_taken": "restock", "action_details": res, "clarification_needed": False}
            else:
                return {"reply": res["error"], "action_taken": "none", "clarification_needed": res.get("clarification_needed", False)}

        # 3. CREDIT
        if intent == "CREDIT" and params.get("customer_name"):
            res = RuleParser.execute_credit(
                customer_query=params["customer_name"],
                product_query=params.get("product_name"),
                quantity=params.get("quantity") or 1,
                amount_override=params.get("amount"),
                raw_query=raw_query
            )
            if res["success"]:
                item_info = f" for {res['quantity']} {res['product_name']}" if res.get("product_name") else ""
                reply = f"Recorded ₹{res['amount_added']:0.2f} on credit for {res['customer_name']}{item_info}. Their total Udhaar is now ₹{res['new_due_balance']:0.2f}."
                return {"reply": reply, "action_taken": "credit", "action_details": res, "clarification_needed": False}
            else:
                return {"reply": res["error"], "action_taken": "none", "clarification_needed": res.get("clarification_needed", False)}

        # 4. PAYMENT
        if intent == "PAYMENT" and params.get("customer_name") and params.get("amount"):
            res = RuleParser.execute_payment(
                customer_query=params["customer_name"],
                amount=params["amount"],
                raw_query=raw_query
            )
            if res["success"]:
                reply = f"Payment noted! {res['customer_name']} paid ₹{res['amount_paid']:0.2f}. Remaining balance: ₹{res['new_due']:0.2f}."
                return {"reply": reply, "action_taken": "payment", "action_details": res, "clarification_needed": False}
            else:
                return {"reply": res["error"], "action_taken": "none", "clarification_needed": res.get("clarification_needed", False)}

        # 5. CREATE_CUSTOMER
        if intent == "CREATE_CUSTOMER" and params.get("customer_name"):
            res = RuleParser.execute_create_customer(
                name=params["customer_name"],
                phone=params.get("phone") or "",
                raw_query=raw_query
            )
            if res["success"]:
                phone_txt = f" (Phone: {res['phone']})" if res.get("phone") else ""
                reply = f"Customer '{res['customer_name']}' has been successfully added to your records{phone_txt}. They are now available for sales and Udhaar transactions."
                return {"reply": reply, "action_taken": "create_customer", "action_details": res, "clarification_needed": False}
            else:
                return {"reply": res["error"], "action_taken": "none", "clarification_needed": res.get("clarification_needed", False)}

        # 6. Queries, greetings, clarifications
        return {
            "reply": llm_reply or "I'm here to help manage your shop. Ask me anything about stock, sales, customers, or record transactions.",
            "action_taken": "query" if intent == "QUERY" else "none",
            "clarification_needed": (intent == "CLARIFICATION")
        }

    @classmethod
    def _extract_quantity(cls, text: str) -> int:
        """Extract numeric quantity or word-based quantity."""
        lower = text.lower()
        # Direct digit
        m = re.search(r"\b(\d+)\b", lower)
        if m:
            return int(m.group(1))
        # Word number
        for word, val in WORD_NUMBERS.items():
            if re.search(rf"\b{word}\b", lower):
                return val
        return 1

    @classmethod
    def _extract_customer_name(cls, cursor, text: str) -> Tuple[Optional[dict], Optional[str]]:
        """Identify matched customer dict and/or raw customer name string."""
        # 1. Direct match with registered customers
        matched_c = match_customer(cursor, text)
        if matched_c:
            return matched_c, matched_c["name"]

        # 2. Extract potential customer name using sentence structure
        patterns = [
            r"^([A-Z][a-zA-Z]+)\s+(?:bought|took|paid|purchased)\b",
            r"\b(?:to|from|for)\s+([A-Z][a-zA-Z]+)\b",
            r"\b([A-Z][a-zA-Z]+)\s+(?:paid|took|bought)\b"
        ]
        for pat in patterns:
            m = re.search(pat, text)
            if m:
                cand = m.group(1).strip()
                # Ensure it's not a stop word
                if cand.lower() not in {"today", "yesterday", "how", "much", "stock", "maggi", "milk", "salt", "atta", "rice"}:
                    c_lookup = match_customer(cursor, cand)
                    if c_lookup:
                        return c_lookup, c_lookup["name"]
                    return None, cand

        return None, None

    @classmethod
    def _extract_new_customer_details(cls, text: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Extract customer name and optional phone from registration phrasing.
        e.g. 'Add new customer Ramesh' -> ('Ramesh', '')
        e.g. 'Add new customer Suresh with phone 9876543210' -> ('Suresh', '9876543210')
        e.g. 'Add Rajesh as a new customer' -> ('Rajesh', '')
        """
        patterns = [
            r'(?:add|create|register)\s+(?:new\s+)?customer\s+([A-Za-z\s]+?)(?:[,\s]+(?:with\s+phone|phone|mobile|number|#)?[:\s]*(\+?\d[\d\s-]{7,}\d))?$',
            r'new\s+customer\s+([A-Za-z\s]+?)(?:[,\s]+(?:with\s+phone|phone|mobile|number|#)?[:\s]*(\+?\d[\d\s-]{7,}\d))?$',
            r'(?:add|create|register)\s+([A-Za-z\s]+?)\s+as\s+(?:a\s+)?(?:new\s+)?customer(?:[,\s]+(?:with\s+phone|phone|mobile|number)?[:\s]*(\+?\d[\d\s-]{7,}\d))?$'
        ]
        clean_text = text.strip()
        for pat in patterns:
            m = re.search(pat, clean_text, re.IGNORECASE)
            if m:
                name = m.group(1).strip()
                phone = m.group(2).strip() if m.group(2) else ""
                name = re.sub(r"[^\w\s]", "", name).strip()
                if len(name) >= 2:
                    return name, phone
        return None, None

    @classmethod
    def _extract_product_info(cls, cursor, text: str, customer_name: str = None) -> Tuple[Optional[dict], str]:
        """Identify matched product dict and candidate product query string."""
        matched_p = match_product(cursor, text)
        if matched_p:
            return matched_p, matched_p["name"]

        candidate = extract_candidate_product(text, customer_name)
        if candidate:
            p_lookup = match_product(cursor, candidate)
            if p_lookup:
                return p_lookup, p_lookup["name"]
            return None, candidate

        return None, ""

    @classmethod
    def _process_local(cls, raw: str, history: List[Dict[str, str]], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Intelligent local fallback engine powered directly by SQLite queries,
        fuzzy matching, natural language intent classification, and strict stock checks.
        """
        lower = raw.lower().strip()
        metrics = context["metrics"]
        products = context["products"]
        customers = context["customers"]

        conn = get_db_connection()
        cursor = conn.cursor()

        matched_c, cust_name = cls._extract_customer_name(cursor, raw)
        matched_p, prod_query = cls._extract_product_info(cursor, raw, cust_name)
        qty = cls._extract_quantity(raw)

        conn.close()

        # ---------------------------------------------------------------------
        # 1. Greetings
        # ---------------------------------------------------------------------
        if re.search(r"^(hi|hello|hey|namaste|kem cho|good morning|good evening)\b", lower):
            return {
                "reply": "Namaste! I'm your Kirana Assistant. I can help record sales, update stock, track Udhaar, and answer any questions about today's shop performance.",
                "action_taken": "none",
                "clarification_needed": False
            }

        # ---------------------------------------------------------------------
        # 2. Sales / Performance Questions
        # ---------------------------------------------------------------------
        if re.search(r"\b(show today'?s sales|today'?s sales|today sales|sales today|how much did i sell|total sales|total sale|revenue today)\b", lower):
            return {
                "reply": f"Today's total sales are ₹{metrics['sales_today']:0.2f} across your registered sales transactions. You've also collected ₹{metrics['payments_today']:0.2f} in Udhaar repayments.",
                "action_taken": "query",
                "clarification_needed": False
            }

        # ---------------------------------------------------------------------
        # 3. Profit Questions
        # ---------------------------------------------------------------------
        if re.search(r"\b(profit|margin|earned|earnings|gain|earning)\b", lower):
            return {
                "reply": f"Your estimated gross profit from today's completed sales is ₹{metrics['profit_today']:0.2f} (based on cost vs selling prices).",
                "action_taken": "query",
                "clarification_needed": False
            }

        # ---------------------------------------------------------------------
        # 4. Low stock / Restock alerts
        # ---------------------------------------------------------------------
        if re.search(r"\b(low.*stock|running low|shortage|need to restock|need to buy|products are running low)\b", lower) and not re.search(r"\b(add|added|restock \d|received)\b", lower):
            low = [p for p in products if p["stock"] <= p["min_stock"]]
            if low:
                items_str = ", ".join([f"{p['name']} ({p['stock']} {p['unit']} left, alert at {p['min_stock']})" for p in low])
                return {
                    "reply": f"You currently have {len(low)} product(s) needing restock: {items_str}.",
                    "action_taken": "query",
                    "clarification_needed": False
                }
            return {
                "reply": "All your inventory levels are currently above minimum alert thresholds! Nothing urgently needs restocking.",
                "action_taken": "query",
                "clarification_needed": False
            }

        # ---------------------------------------------------------------------
        # 5. Who owes me / Udhaar questions
        # ---------------------------------------------------------------------
        if re.search(r"\b(who owes|who has due|pending money|total udhaar|list credit|who owes me)\b", lower) and not re.search(r"\b(paid|took|bought|sold)\b", lower):
            due_customers = [c for c in customers if c["due"] > 0]
            if not due_customers:
                return {
                    "reply": "Great news! No customers currently have outstanding Udhaar. All accounts are settled.",
                    "action_taken": "query",
                    "clarification_needed": False
                }
            names_summary = ", ".join([f"{c['name']} (₹{c['due']:0.2f})" for c in due_customers[:3]])
            return {
                "reply": f"You have {len(due_customers)} customer(s) with pending credit totaling ₹{metrics['total_outstanding_udhaar']:0.2f}. Top balances: {names_summary}.",
                "action_taken": "query",
                "clarification_needed": False
            }

        # ---------------------------------------------------------------------
        # 6. Specific Stock Query (e.g. "How much Maggi is left?", "Check milk stock")
        # ---------------------------------------------------------------------
        if re.search(r"\b(how much|how many|is left|check stock|in stock|stock of|do we have|available)\b", lower) and not re.search(r"\b(add|added|bought|sold|took|paid|credit)\b", lower):
            if matched_p:
                if matched_p["stock"] == 0:
                    status_text = "Out of Stock"
                elif matched_p["stock"] <= matched_p["min_stock"]:
                    status_text = "Low stock"
                else:
                    status_text = "In stock"
                return {
                    "reply": f"You have {matched_p['stock']} {matched_p['unit']}(s) of {matched_p['name']} in stock. Selling price is ₹{matched_p['price']:0.2f} per {matched_p['unit']} (Status: {status_text}).",
                    "action_taken": "query",
                    "clarification_needed": False
                }
            elif prod_query:
                verb = "are" if prod_query.lower().endswith("s") else "is"
                return {
                    "reply": f"Product Not Found: {prod_query} {verb} not listed in your inventory. Please check the product name or add the product first.",
                    "action_taken": "none",
                    "clarification_needed": False
                }
            else:
                return {
                    "reply": "Which product's stock would you like to check? (e.g. 'How much Maggi is left?').",
                    "action_taken": "none",
                    "clarification_needed": True
                }

        # ---------------------------------------------------------------------
        # 7. Action: CUSTOMER REGISTRATION
        # e.g. "Add new customer Ramesh", "Add customer Priya", "New customer Suresh"
        # ---------------------------------------------------------------------
        is_customer_registration = bool(
            re.search(r"\b(add|create|register|new)\b.*\b(customer|client)\b", lower) or
            re.search(r"\b(customer|client)\b.*\b(add|create|register|new)\b", lower)
        ) and not re.search(r"\b(bought|buy|buys|sold|sell|sale|took|paid|payment|credit|udhaar)\b", lower)

        if is_customer_registration:
            new_name, new_phone = cls._extract_new_customer_details(raw)
            if not new_name:
                return {
                    "reply": "What is the new customer's name? Please specify their name (e.g. 'Add new customer Ramesh').",
                    "action_taken": "none",
                    "clarification_needed": True
                }

            res = RuleParser.execute_create_customer(new_name, new_phone, raw)
            if res["success"]:
                phone_txt = f" (Phone: {res['phone']})" if res.get("phone") else ""
                return {
                    "reply": f"Customer '{res['customer_name']}' has been successfully added to your records{phone_txt}. They are now available for sales and Udhaar transactions.",
                    "action_taken": "create_customer",
                    "action_details": res,
                    "clarification_needed": False
                }
            return {
                "reply": res["error"],
                "action_taken": "none",
                "clarification_needed": False
            }

        # ---------------------------------------------------------------------
        # 8. Action: STOCK ADDITIONS / RESTOCK
        # e.g. "Add 10 Maggi packets to stock", "Received 15 Tata Salt in stock", "Restock 20 milk"
        # Rule: Do not interpret customer buying a product as stock addition!
        # ---------------------------------------------------------------------
        is_explicit_restock = bool(
            re.search(r"\b(add|added|received)\b.*\b(to stock|in stock|into stock|inventory)\b", lower) or
            re.search(r"\b(restock|replenish)\b", lower)
        )
        if is_explicit_restock:
            if not matched_p and not prod_query:
                return {
                    "reply": "Which product would you like to add to stock? Please specify the product name (e.g. 'Add 10 Maggi packets to stock').",
                    "action_taken": "none",
                    "clarification_needed": True
                }
            target_prod = matched_p["name"] if matched_p else prod_query
            res = RuleParser.execute_restock(target_prod, qty, raw)
            if res["success"]:
                return {
                    "reply": f"Stock updated! Added {res['quantity_added']} {res['unit']}(s) to {res['product_name']}. New inventory count: {res['new_stock']}.",
                    "action_taken": "restock",
                    "action_details": res,
                    "clarification_needed": False
                }
            return {
                "reply": res["error"],
                "action_taken": "none",
                "clarification_needed": res.get("clarification_needed", False)
            }

        # ---------------------------------------------------------------------
        # 8. Action: CUSTOMER CREDIT (UDHAAR)
        # e.g. "Deeksha took 2 Maggi on credit", "Ramesh took 2 rice on credit", "Amit credit ₹250"
        # ---------------------------------------------------------------------
        is_credit = bool(
            re.search(r"\b(on credit|credit|udhaar|khata|baki)\b", lower) or
            re.search(r"\b(took|taken)\b.*\b(on credit|credit|udhaar)\b", lower)
        )
        if is_credit:
            if not cust_name:
                return {
                    "reply": "Which customer took items on credit? Please specify their name (e.g. 'Deeksha took 2 Maggi on credit').",
                    "action_taken": "none",
                    "clarification_needed": True
                }

            amount_match = re.search(r"(?:₹|rs\.?\s*)(\d+(?:\.\d+)?)", lower)
            amount_override = float(amount_match.group(1)) if amount_match else None

            if not matched_p and not prod_query and not amount_override:
                return {
                    "reply": f"What did {cust_name} take on credit? Please specify the product or amount (e.g. '{cust_name} took 2 Maggi on credit').",
                    "action_taken": "none",
                    "clarification_needed": True
                }

            target_prod = matched_p["name"] if matched_p else (prod_query if prod_query else None)
            res = RuleParser.execute_credit(cust_name, target_prod, qty, amount_override, raw)
            if res["success"]:
                item_info = f" for {res['quantity']} {res['product_name']}" if res.get("product_name") else ""
                return {
                    "reply": f"Recorded ₹{res['amount_added']:0.2f} on credit for {res['customer_name']}{item_info}. Their total Udhaar is now ₹{res['new_due_balance']:0.2f}.",
                    "action_taken": "credit",
                    "action_details": res,
                    "clarification_needed": False
                }
            return {
                "reply": res["error"],
                "action_taken": "none",
                "clarification_needed": res.get("clarification_needed", False)
            }

        # ---------------------------------------------------------------------
        # 9. Action: CUSTOMER PAYMENT
        # e.g. "Deeksha paid 100", "Ramesh paid 200", "Sunita settled 500"
        # ---------------------------------------------------------------------
        is_payment = bool(re.search(r"\b(paid|payment|settled|repaid|cleared)\b", lower))
        if is_payment:
            amount_match = re.search(r"(?:₹|rs\.?\s*)?(\d+(?:\.\d+)?)", lower)
            # Find number that is not quantity near words
            amount = float(amount_match.group(1)) if amount_match else 0.0

            if not cust_name:
                return {
                    "reply": "Who made the payment? Please specify the customer name (e.g. 'Deeksha paid 100').",
                    "action_taken": "none",
                    "clarification_needed": True
                }
            if amount <= 0:
                return {
                    "reply": f"How much did {cust_name} pay? Please specify the amount (e.g. '{cust_name} paid 100').",
                    "action_taken": "none",
                    "clarification_needed": True
                }

            res = RuleParser.execute_payment(cust_name, amount, raw)
            if res["success"]:
                return {
                    "reply": f"Payment noted! {res['customer_name']} paid ₹{res['amount_paid']:0.2f}. Remaining balance: ₹{res['new_due']:0.2f}.",
                    "action_taken": "payment",
                    "action_details": res,
                    "clarification_needed": False
                }
            return {
                "reply": res["error"],
                "action_taken": "none",
                "clarification_needed": res.get("clarification_needed", False)
            }

        # ---------------------------------------------------------------------
        # 10. Ambiguity Check: "took" without specifying cash or credit
        # e.g. "Deeksha took 2 Maggi"
        # ---------------------------------------------------------------------
        if re.search(r"\b(took|takes|taken)\b", lower) and not re.search(r"\b(credit|udhaar|cash|paid)\b", lower):
            prod_name = matched_p["name"] if matched_p else (prod_query if prod_query else "items")
            customer_label = cust_name if cust_name else "the customer"
            return {
                "reply": f"Did {customer_label} pay cash or take {qty} {prod_name} on credit?",
                "action_taken": "none",
                "clarification_needed": True
            }

        # ---------------------------------------------------------------------
        # 11. Action: SALES (e.g. "Deeksha bought 2 maggie", "Sold 2 Maggi to Deeksha", "Sold 2 Chocolate bars")
        # ---------------------------------------------------------------------
        is_sale = bool(re.search(r"\b(bought|buy|buys|purchased|purchase|sold|sell|sale|sells)\b", lower))
        if is_sale:
            if not matched_p and not prod_query:
                return {
                    "reply": "Which product did you sell? Please specify the product name (e.g. 'Sold 2 Maggi').",
                    "action_taken": "none",
                    "clarification_needed": True
                }

            target_prod = matched_p["name"] if matched_p else prod_query
            res = RuleParser.execute_sale(target_prod, qty, raw, cust_name)
            if res["success"]:
                cust_info = f" to {res['customer_name']}" if res.get("customer_name") else ""
                reply = f"Recorded sale of {qty} {res['unit']}(s) of {res['product_name']}{cust_info} (₹{res['total_amount']:0.2f}). Remaining stock: {res['remaining_stock']}."
                if res.get("warning"):
                    reply += f" ⚠️ {res['warning']}"
                return {
                    "reply": reply,
                    "action_taken": "sale",
                    "action_details": res,
                    "clarification_needed": False
                }
            return {
                "reply": res["error"],
                "action_taken": "none",
                "clarification_needed": res.get("clarification_needed", False)
            }

        # ---------------------------------------------------------------------
        # 12. Unidentified product or ambiguous action
        # ---------------------------------------------------------------------
        if matched_p and not is_sale and not is_credit and not is_explicit_restock:
            return {
                "reply": f"Would you like to record a sale of {qty} {matched_p['name']}, add them to stock, or record them on credit?",
                "action_taken": "none",
                "clarification_needed": True
            }

        # ---------------------------------------------------------------------
        # 13. Helpful contextual fallback (Never raw "I heard...")
        # ---------------------------------------------------------------------
        return {
            "reply": "I couldn't quite understand that transaction. You can record sales (e.g. 'Deeksha bought 2 Maggi'), credit (e.g. 'Deeksha took 2 Maggi on credit'), payments (e.g. 'Deeksha paid 100'), add stock (e.g. 'Add 10 Maggi packets to stock'), or ask about sales and stock.",
            "action_taken": "none",
            "clarification_needed": True
        }
