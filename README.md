# Kirana Chat Ledger (किराना चैट लेजर)

> Intelligent, chat-first ledger and inventory management web application for Indian kirana store shopkeepers. Powered by **React**, **FastAPI**, **SQLite**, and **LLM API integration**.

Shopkeepers can ask questions and record business operations naturally:
- **Sales**: *"Sold 2 Maggi"*, *"Sell 3 milk packets"*
- **Inventory & Restocking**: *"Received 15 Tata Salt in stock"*, *"Add 10 oil"*
- **Customer Credit (Udhaar)**: *"Ramesh took 1 milk on credit"*, *"Sunita credit ₹250"*
- **Repayments**: *"Ramesh paid 100"*, *"Sunita settled ₹500"*
- **Business Performance Queries**:
  - *"How much did I sell today?"*
  - *"What is my profit today?"*
  - *"Which products are running low on stock?"*
  - *"Who owes me the most money?"*
  - *"How much Maggi do I have left?"*
- **Conversational Queries**: Friendly greetings (*"Namaste"*, *"Good morning"*), follow-up questions, and shop advice.

---

## Architecture & Intelligence Design

The application uses a **hybrid intelligence system**:
1. **LLM Engine (Gemini / OpenAI API)**:
   - Understands colloquial shop phrasing, multilingual mixes (Hinglish/English), spelling variations, and contextual follow-ups.
   - Generates warm, friendly, human-like shopkeeper responses.
   - Keys are configured via environment variables (`GEMINI_API_KEY` / `GOOGLE_API_KEY` or `OPENAI_API_KEY`), never exposed in frontend code.
2. **SQLite Database (Ground-Truth Source of Truth)**:
   - All business figures (sales, profits, inventory counts, credit balances) come directly from live SQLite records.
   - **Zero Hallucination**: The LLM is provided live database context and instructed never to invent business numbers.
3. **Deterministic Rule Parser & Transaction Safety**:
   - Write actions (sales, stock deductions, credit additions, repayments) are validated before execution.
   - Stock cannot go negative. Unmatched items or ambiguous instructions trigger friendly clarification questions.
4. **Built-in Smart Local NLP Fallback**:
   - If no LLM API key is configured or offline, the built-in local engine seamlessly answers queries from SQLite records and executes operations safely with fuzzy matching.

---

## Quickstart

### 1. Backend Setup (FastAPI & SQLite)
```powershell
cd kirana-chat-ledger\backend

# (Optional) Set your Gemini API key for advanced conversational AI:
$env:GEMINI_API_KEY="your_api_key_here"

# Start FastAPI server on port 8000:
python main.py
```
*Backend runs at `http://127.0.0.1:8000`. You can inspect interactive API documentation at `http://127.0.0.1:8000/docs`.*

### 2. Frontend Setup (React & Vite)
```powershell
cd kirana-chat-ledger

# Start the Vite development server (proxies /api to port 8000):
npm run dev
```
*Open **`http://localhost:5173/assistant`** in your browser to chat with the assistant.*

---

## Running Automated Tests

Run the comprehensive test suite (12 test cases covering health, live store queries, sale execution, credit tracking, repayments, fuzzy spelling tolerance, and clarification prompts):

```powershell
cd kirana-chat-ledger\backend
python -m unittest tests/test_chat_api.py
```

---

## API Endpoints

- **`GET /api/health`**: Service status, database check, and LLM provider indicator.
- **`GET /api/store/state`**: Ground-truth snapshot of products, customers, transactions, and metrics.
- **`POST /api/chat`**: Process shopkeeper message with conversation memory and return updated store state.
- **`POST /api/products`**: Add new inventory item.
- **`POST /api/customers`**: Add customer account.
- **`POST /api/transactions/payment`**: Record credit repayment.
- **`POST /api/inventory/adjust`**: Adjust stock level.
