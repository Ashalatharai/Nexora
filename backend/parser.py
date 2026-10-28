import re
from datetime import datetime
from database import get_db_connection, db_transaction, dict_from_row

def _levenshtein_distance(s1: str, s2: str) -> int:
    """Compute Levenshtein edit distance between two strings."""
    s1, s2 = s1.lower(), s2.lower()
    if len(s1) < len(s2):
        return _levenshtein_distance(s2, s1)
    if len(s2) == 0:
        return len(s1)

    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row

    return previous_row[-1]

STOP_WORDS = {
    "today", "yesterday", "how", "much", "many", "what", "which", "check", "stock",
    "have", "left", "give", "show", "price", "did", "sell", "sold", "bought", "buy",
    "buys", "purchased", "purchase", "credit", "udhaar", "paid", "customer", "please",
    "item", "items", "packet", "packets", "take", "took", "to", "for", "from", "on",
    "in", "the", "a", "an", "is", "of", "and", "add", "added", "restock", "receive",
    "received", "bars", "bar", "bottle", "bottles", "litre", "litres", "kg", "kgs"
}

# Common Kirana product synonyms & aliases
PRODUCT_SYNONYMS = {
    "maggie": "maggi",
    "noodles": "maggi",
    "noodle": "maggi",
    "milk": "amul taaza milk",
    "taaza": "amul taaza milk",
    "salt": "tata salt",
    "oil": "fortune sunflower oil",
    "sunflower": "fortune sunflower oil",
    "atta": "aashirvaad atta",
    "flour": "aashirvaad atta",
    "biscuit": "parle-g biscuits",
    "biscuits": "parle-g biscuits",
    "parleg": "parle-g biscuits",
    "parle": "parle-g biscuits",
    "rice": "india gate basmati rice",
    "basmati": "india gate basmati rice",
    "surf": "surf excel easy wash",
    "excel": "surf excel easy wash",
    "soap": "surf excel easy wash",
    "detergent": "surf excel easy wash",
    "butter": "amul butter",
    "cookies": "good day cookies",
    "cookie": "good day cookies",
    "goodday": "good day cookies",
}

def match_product(cursor, query: str):
    """
    Find product with high tolerance for spelling mistakes, partial words, and synonyms.
    """
    q = query.strip().lower()
    if not q:
        return None

    cursor.execute("SELECT * FROM products")
    products = [dict_from_row(row) for row in cursor.fetchall()]

    # 1. Exact match on name or sku
    for p in products:
        if p["name"].lower() == q or p["sku"].lower() == q:
            return p

    # 2. Check synonyms
    q_words = [w for w in re.findall(r"\w+", q) if w not in STOP_WORDS]
    for qw in q_words:
        if qw in PRODUCT_SYNONYMS:
            syn_target = PRODUCT_SYNONYMS[qw]
            for p in products:
                if syn_target in p["name"].lower():
                    return p

    # 3. Token / word containment and Levenshtein scoring
    scored = []
    for p in products:
        p_name = p["name"].lower()
        p_words = [w for w in re.findall(r"\w+", p_name) if w not in STOP_WORDS]
        score = 0

        # Substring match
        for pw in p_words:
            if len(pw) >= 3 and pw in q:
                score += 15

        # Word-level overlap & fuzzy match
        for qw in q_words:
            if len(qw) >= 3:
                for pw in p_words:
                    if qw == pw:
                        score += 15
                    elif qw in pw or pw in qw:
                        score += 8
                    elif _levenshtein_distance(qw, pw) <= 1:
                        score += 10
                    elif len(qw) >= 5 and _levenshtein_distance(qw, pw) <= 2:
                        score += 6

        if score > 0:
            scored.append((score, p))

    if scored:
        scored.sort(key=lambda x: x[0], reverse=True)
        # Threshold check: ensure highest score is meaningful
        if scored[0][0] >= 6:
            return scored[0][1]

    return None

def match_customer(cursor, query: str):
    """
    Find customer with spelling and first-name tolerance (e.g. 'Deeksha' or 'Ramesh').
    """
    q = query.strip().lower()
    if not q:
        return None

    cursor.execute("SELECT * FROM customers")
    customers = [dict_from_row(row) for row in cursor.fetchall()]

    # 1. Exact match
    for c in customers:
        if c["name"].lower() == q or c["phone"] == q:
            return c

    # 2. First name match or token match
    q_words = re.findall(r"\w+", q)
    scored = []
    for c in customers:
        c_name = c["name"].lower()
        c_words = re.findall(r"\w+", c_name)
        score = 0

        if q in c_name:
            score += 20

        for qw in q_words:
            for cw in c_words:
                if qw == cw:
                    score += 15
                elif _levenshtein_distance(qw, cw) <= 1 and len(qw) >= 4:
                    score += 10

        if score > 0:
            scored.append((score, c))

    if scored:
        scored.sort(key=lambda x: x[0], reverse=True)
        if scored[0][0] >= 10:
            return scored[0][1]

    return None

def extract_candidate_product(raw_text: str, customer_name: str = None) -> str:
    """
    Extract the raw product phrase from a sentence when not found in catalogue.
    e.g. 'Sold 2 Chocolate bars to Deeksha' -> 'Chocolate bars'
    """
    text = raw_text.strip()
    if customer_name:
        text = re.sub(re.escape(customer_name), "", text, flags=re.IGNORECASE)

    # Strip numbers / quantities
    text = re.sub(r"\b\d+\b", "", text)
    # Strip "packets of", "packs of", metric units (kg, litre)
    text = re.sub(r"\b(packets?\s+of|packs?\s+of|bottles?\s+of|boxes?\s+of|kg|kgs|litres?|litre)\b", "", text, flags=re.IGNORECASE)
    # Strip action / grammatical words
    text = re.sub(r"\b(sold|sell|sale|bought|buy|buys|purchased|purchase|took|takes|add|added|restock|replenish|received|credit|udhaar|paid|payment|stock|left|in\s+stock|to\s+stock|how\s+much|how\s+many|show|today'?s|to|for|from|on|in|of|the|a|an|is|are|please)\b", "", text, flags=re.IGNORECASE)
    # Clean non-alphanumeric punctuation
    cleaned = re.sub(r"[^\w\s-]", " ", text).strip()
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned if len(cleaned) >= 2 else ""

class RuleParser:
    @staticmethod
    def execute_sale(product_query: str, quantity: int = 1, raw_query: str = "", customer_query: str = None) -> dict:
        """
        Safely execute sale:
        - Validates product existence
        - Validates sufficient inventory (>0 and >= requested)
        - Never reduces stock below zero
        - Never records sale if stock insufficient or product not found
        - Connects customer name if provided
        """
        quantity = max(1, int(quantity))
        with db_transaction() as conn:
            cursor = conn.cursor()
            product = match_product(cursor, product_query)

            # 1. Product Not Found
            if not product:
                display_name = product_query if product_query else "Requested item"
                verb = "are" if display_name.lower().endswith("s") else "is"
                return {
                    "success": False,
                    "error_type": "PRODUCT_NOT_FOUND",
                    "error": f"Product Not Found: {display_name} {verb} not listed in your inventory. Please check the product name or add the product first.",
                    "clarification_needed": False
                }

            # 2. Out of Stock (stock == 0)
            if product["stock"] == 0:
                return {
                    "success": False,
                    "error_type": "OUT_OF_STOCK",
                    "error": f"{product['name']} is Out of Stock. No sale was recorded.",
                    "clarification_needed": False,
                    "available_stock": 0
                }

            # 3. Insufficient Stock (0 < stock < quantity)
            if product["stock"] < quantity:
                return {
                    "success": False,
                    "error_type": "INSUFFICIENT_STOCK",
                    "error": f"Insufficient Stock: Only {product['stock']} {product['name']} {product['unit']}(s) are available, but you requested {quantity}. No sale was recorded.",
                    "clarification_needed": False,
                    "available_stock": product["stock"]
                }

            # 4. Valid Sale - deduct inventory and record transaction
            new_stock = product["stock"] - quantity
            total_amount = round(product["price"] * quantity, 2)
            profit = round((product["price"] - product.get("cost_price", 0)) * quantity, 2)
            now_time = datetime.now().strftime("%I:%M %p")

            cursor.execute(
                "UPDATE products SET stock = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (new_stock, product["id"])
            )

            # Link customer if known
            customer = match_customer(cursor, customer_query) if customer_query else None
            cust_id = customer["id"] if customer else None
            cust_label = customer["name"] if customer else (customer_query.strip() if customer_query else "")
            detail_suffix = f" ({cust_label})" if cust_label else ""

            tx_id = f"t{int(datetime.now().timestamp() * 1000)}"
            cursor.execute("""
                INSERT INTO transactions (id, customer_id, title, detail, amount, profit, type, time, date, raw_query)
                VALUES (?, ?, ?, ?, ?, ?, 'sale', ?, 'Today', ?)
            """, (
                tx_id,
                cust_id,
                f"{product['name']} sold",
                f"{quantity} {product['unit']}{'s' if quantity > 1 else ''} · Cash sale{detail_suffix}",
                total_amount,
                profit,
                now_time,
                raw_query
            ))

        warning = None
        if new_stock <= product["min_stock"]:
            warning = f"Low stock alert: {product['name']} has only {new_stock} {product['unit']}(s) remaining."

        return {
            "success": True,
            "product_id": product["id"],
            "product_name": product["name"],
            "unit": product["unit"],
            "unit_price": product["price"],
            "quantity": quantity,
            "total_amount": total_amount,
            "profit": profit,
            "remaining_stock": new_stock,
            "customer_name": cust_label or None,
            "warning": warning
        }

    @staticmethod
    def execute_restock(product_query: str, quantity: int = 1, raw_query: str = "") -> dict:
        """Safely replenish stock for an existing product."""
        quantity = max(1, int(quantity))
        with db_transaction() as conn:
            cursor = conn.cursor()
            product = match_product(cursor, product_query)
            if not product:
                display_name = product_query if product_query else "Requested item"
                verb = "are" if display_name.lower().endswith("s") else "is"
                return {
                    "success": False,
                    "error_type": "PRODUCT_NOT_FOUND",
                    "error": f"Product Not Found: {display_name} {verb} not listed in your inventory. Please check the product name or add the product first.",
                    "clarification_needed": False
                }

            new_stock = product["stock"] + quantity
            cursor.execute(
                "UPDATE products SET stock = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (new_stock, product["id"])
            )

            now_time = datetime.now().strftime("%I:%M %p")
            tx_id = f"t{int(datetime.now().timestamp() * 1000)}"
            cursor.execute("""
                INSERT INTO transactions (id, customer_id, title, detail, amount, profit, type, time, date, raw_query)
                VALUES (?, NULL, ?, ?, ?, 0.0, 'restock', ?, 'Today', ?)
            """, (
                tx_id,
                f"{product['name']} restocked",
                f"+{quantity} {product['unit']}{'s' if quantity > 1 else ''} received in stock",
                0.0,
                now_time,
                raw_query
            ))

        return {
            "success": True,
            "product_id": product["id"],
            "product_name": product["name"],
            "unit": product["unit"],
            "quantity_added": quantity,
            "new_stock": new_stock
        }

    @staticmethod
    def execute_credit(customer_query: str, product_query: str = None, quantity: int = 1, amount_override: float = None, raw_query: str = "") -> dict:
        """
        Safely record a credit (udhaar) transaction:
        - Validates customer exists
        - If product provided: validates stock availability FIRST!
        - If stock is 0 or insufficient, does NOT record transaction
        """
        quantity = max(1, int(quantity))
        with db_transaction() as conn:
            cursor = conn.cursor()

            # 1. Customer verification
            customer = match_customer(cursor, customer_query) if customer_query else None
            if not customer:
                c_name = customer_query.strip() if customer_query else "Unknown"
                return {
                    "success": False,
                    "error_type": "CUSTOMER_NOT_FOUND",
                    "error": f"Customer Not Found: '{c_name}' is not in your customer records. Please check the name or add the customer first.",
                    "clarification_needed": True
                }

            # 2. Product verification and stock check (if product specified)
            product = None
            if product_query:
                product = match_product(cursor, product_query)
                if not product:
                    verb = "are" if product_query.lower().endswith("s") else "is"
                    return {
                        "success": False,
                        "error_type": "PRODUCT_NOT_FOUND",
                        "error": f"Product Not Found: {product_query} {verb} not listed in your inventory. Please check the product name or add the product first.",
                        "clarification_needed": False
                    }

                if product["stock"] == 0:
                    return {
                        "success": False,
                        "error_type": "OUT_OF_STOCK",
                        "error": f"{product['name']} is Out of Stock. No credit transaction was recorded.",
                        "clarification_needed": False,
                        "available_stock": 0
                    }

                if product["stock"] < quantity:
                    return {
                        "success": False,
                        "error_type": "INSUFFICIENT_STOCK",
                        "error": f"Insufficient Stock: Only {product['stock']} {product['name']} {product['unit']}(s) are available, but you requested {quantity}. No credit transaction was recorded.",
                        "clarification_needed": False,
                        "available_stock": product["stock"]
                    }

            # 3. Determine amount
            if amount_override is not None and amount_override > 0:
                total_amount = round(float(amount_override), 2)
            elif product:
                total_amount = round(product["price"] * quantity, 2)
            else:
                total_amount = 0.0

            if total_amount <= 0:
                return {
                    "success": False,
                    "error": "Could not determine credit amount. Please mention the item or rupee amount.",
                    "clarification_needed": True
                }

            # 4. Update customer balance
            new_due = round(customer["due"] + total_amount, 2)
            cursor.execute(
                "UPDATE customers SET due = ?, last_active = 'Today', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (new_due, customer["id"])
            )

            # 5. Deduct product stock if product was sold on credit
            new_stock = None
            if product:
                new_stock = product["stock"] - quantity
                cursor.execute(
                    "UPDATE products SET stock = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (new_stock, product["id"])
                )

            now_time = datetime.now().strftime("%I:%M %p")
            tx_id = f"t{int(datetime.now().timestamp() * 1000)}"
            cursor.execute("""
                INSERT INTO transactions (id, customer_id, title, detail, amount, profit, type, time, date, raw_query)
                VALUES (?, ?, 'Udhaar added', ?, ?, 0.0, 'credit', ?, 'Today', ?)
            """, (
                tx_id,
                customer["id"],
                f"{customer['name']} · {quantity} {product['name'] if product else 'items'}",
                total_amount,
                now_time,
                raw_query
            ))

        return {
            "success": True,
            "customer_id": customer["id"],
            "customer_name": customer["name"],
            "amount_added": total_amount,
            "new_due_balance": new_due,
            "product_name": product["name"] if product else None,
            "quantity": quantity if product else None,
            "remaining_stock": new_stock
        }

    @staticmethod
    def execute_payment(customer_query: str, amount: float, raw_query: str = "") -> dict:
        """Safely record a customer repayment towards credit."""
        try:
            amount = round(float(amount), 2)
            if amount <= 0:
                return {"success": False, "error": "Repayment amount must be greater than zero.", "clarification_needed": True}
        except (ValueError, TypeError):
            return {"success": False, "error": "Valid numerical payment amount required.", "clarification_needed": True}

        with db_transaction() as conn:
            cursor = conn.cursor()
            customer = match_customer(cursor, customer_query) if customer_query else None
            if not customer:
                c_name = customer_query.strip() if customer_query else "Unknown"
                return {
                    "success": False,
                    "error_type": "CUSTOMER_NOT_FOUND",
                    "error": f"Customer Not Found: '{c_name}' is not in your customer records. Please verify the customer name.",
                    "clarification_needed": True
                }

            new_due = max(0.0, round(customer["due"] - amount, 2))
            cursor.execute(
                "UPDATE customers SET due = ?, last_active = 'Today', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (new_due, customer["id"])
            )

            now_time = datetime.now().strftime("%I:%M %p")
            tx_id = f"t{int(datetime.now().timestamp() * 1000)}"
            cursor.execute("""
                INSERT INTO transactions (id, customer_id, title, detail, amount, profit, type, time, date, raw_query)
                VALUES (?, ?, 'Udhaar payment received', ?, ?, 0.0, 'payment', ?, 'Today', ?)
            """, (
                tx_id,
                customer["id"],
                f"{customer['name']} · Cash/UPI",
                amount,
                now_time,
                raw_query
            ))

        return {
            "success": True,
            "customer_id": customer["id"],
            "customer_name": customer["name"],
            "amount_paid": amount,
            "previous_due": customer["due"],
            "new_due": new_due
        }

    @staticmethod
    def execute_create_customer(name: str, phone: str = "", raw_query: str = "") -> dict:
        """
        Safely registers a new customer in SQLite:
        - Prevents duplicates by exact name or phone number
        - Returns existing customer info if duplicate detected
        - Saves new customer with initial due 0.0
        """
        name_clean = name.strip()
        phone_clean = phone.strip()
        if not name_clean:
            return {
                "success": False,
                "error": "Customer name is required.",
                "clarification_needed": True
            }

        with db_transaction() as conn:
            cursor = conn.cursor()

            # 1. Duplicate check by name (case-insensitive exact match)
            cursor.execute("SELECT * FROM customers WHERE LOWER(TRIM(name)) = LOWER(TRIM(?))", (name_clean,))
            existing = cursor.fetchone()
            if existing:
                cust = dict_from_row(existing)
                phone_str = f" (Phone: {cust['phone']})" if cust.get("phone") else ""
                due_str = f", current Udhaar: ₹{cust['due']:.2f}" if cust.get("due", 0) > 0 else ""
                return {
                    "success": False,
                    "error_type": "CUSTOMER_ALREADY_EXISTS",
                    "error": f"Customer '{cust['name']}' already exists in your records{phone_str}{due_str}. No duplicate was created.",
                    "customer": cust,
                    "clarification_needed": False
                }

            # 2. Duplicate check by phone (if provided)
            if phone_clean:
                clean_digits = re.sub(r"\D", "", phone_clean)
                if len(clean_digits) >= 10:
                    cursor.execute("SELECT * FROM customers WHERE phone != ''")
                    for row in cursor.fetchall():
                        existing_phone_digits = re.sub(r"\D", "", row["phone"])
                        if existing_phone_digits and existing_phone_digits[-10:] == clean_digits[-10:]:
                            cust = dict_from_row(row)
                            return {
                                "success": False,
                                "error_type": "CUSTOMER_ALREADY_EXISTS",
                                "error": f"A customer with phone '{phone_clean}' already exists in your records ({cust['name']}). No duplicate was created.",
                                "customer": cust,
                                "clarification_needed": False
                            }

            # 3. Create new customer
            cid = f"c{int(datetime.now().timestamp() * 1000)}"
            words = name_clean.split()
            initials = "".join([w[0].upper() for w in words[:2]]) or name_clean[:2].upper()
            colors = ["mint", "lavender", "peach", "blue", "sand", "rose"]
            color = colors[int(datetime.now().timestamp()) % len(colors)]

            cursor.execute("""
                INSERT INTO customers (id, name, phone, due, last_active, initials, color)
                VALUES (?, ?, ?, 0.0, 'Today', ?, ?)
            """, (cid, name_clean, phone_clean, initials, color))

        return {
            "success": True,
            "customer_id": cid,
            "customer_name": name_clean,
            "phone": phone_clean,
            "initials": initials,
            "color": color
        }
