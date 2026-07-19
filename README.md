# AlokSaar — AI Pharmacy Business Copilot

*Illuminate every decision. Empower every pharmacy.*

A conversational AI Pharmacy Business Copilot, ChatGPT/Gemini-style — handles
natural conversation (greetings, small talk) as well as grounded business
analysis (profit, inventory, expiry, purchasing, compliance), backed by a
real Flask + SQLAlchemy backend, a RAG knowledge base (ChromaDB), and live
business analytics.

## Quick start (fastest path — SQLite, zero setup)

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env and add your GEMINI_API_KEY (free — https://aistudio.google.com/apikey)

python -m data.seed             # creates aloksaar.db automatically, fills it with demo data
python run.py
```

Visit **http://localhost:5000** for the dashboard, or
**http://localhost:5000/chat** for the AI Copilot chat.

No database server, no Postgres, no account setup beyond a free Gemini API
key. `aloksaar.db` is a single SQLite file created automatically in the
project folder.

## What the chatbot can do

- **Natural conversation** — say hi, make small talk, ask what it can do. \
It replies like ChatGPT/Gemini would: warm, brief, no forced business data \
dump into a casual greeting.
- **Grounded business analysis** — ask about profit, inventory, expiry risk, \
dead stock, purchasing, or compliance, and it answers using your actual \
database numbers plus a RAG knowledge base (drug info, SOPs, compliance \
policy) — never invented figures.
- **Markdown-formatted answers** — tables, bullets, bold, rendered properly \
in the chat UI (not raw `**`/`###` symbols).
- **Short by default** — key facts + 2-3 action items; expands only if you \
ask for more detail.

## Architecture

Follows a layered conversational pipeline (matches the architecture diagram):

```
Pharmacy Owner
   │
   ▼
Frontend (Chat Interface)
   │
   ▼
Flask Route (app/routes/chat.py)
   │
   ▼
Conversation Manager (app/services/conversation_manager.py)
   │
   ├─ Memory (app/services/memory.py) ─────── loads/saves chat history
   │
   ├─ Intent Service (app/services/intent_service.py)
   │     classifies into: greeting / general_chat / business / medicine / mixed
   │
   ├─ Context Builder (app/services/context_builder.py)
   │     ├─ Business data (app/services/analytics.py, forecasting.py)
   │     ├─ Recommendations (app/services/planner.py)
   │     └─ RAG retrieval (app/rag/retriever.py — ChromaDB)
   │
   └─ Tool Executor (app/services/tool_executor.py)
         calls Gemini (default) or Anthropic → natural language response
   │
   ▼
Memory saves the turn → JSON response → Frontend displays reply
```

**Why intent-based routing matters:** a greeting ("hi") skips business/RAG
context entirely and gets a fast, natural reply — no data dump forced into
small talk. A business question ("why is my profit low") pulls live
database numbers plus pre-ranked recommendations from the planner. A
medicine/compliance question pulls RAG knowledge-base excerpts. A mixed
question gets both. This routing happens via lightweight keyword rules in
`intent_service.py` — no extra LLM call needed just to classify intent,
keeping responses fast.

## Tech stack

- **Backend**: Python, Flask, SQLAlchemy
- **Database**: SQLite by default (zero setup) — swap to PostgreSQL/Neon via \
`DATABASE_URL` in `.env` if you want a real server-backed DB later
- **Vector store**: ChromaDB (RAG knowledge base)
- **AI**: Google Gemini (free tier, default) or Anthropic Claude (optional, \
paid) — switch via `LLM_PROVIDER` in `.env`
- **Frontend**: Server-rendered Jinja templates + vanilla JS + Chart.js + \
marked.js/DOMPurify for safe Markdown rendering

## Switching to PostgreSQL later

Uncomment and fill in `DATABASE_URL` in `.env`:
```dotenv
DATABASE_URL=postgresql://user:password@host:5432/dbname
```
Then re-run `python -m data.seed` against the new database. Everything else
(routes, models, business logic) works identically against either database.

## Project layout

```
aloksaar/
├── run.py                      # entrypoint
├── config.py                   # env-driven configuration (SQLite by default)
├── requirements.txt
├── .env.example
├── app/
│   ├── __init__.py              # Flask app factory
│   ├── extensions.py            # shared SQLAlchemy instance
│   ├── models/                  # Medicine, StockBatch, Supplier, Sale,
│   │                             # Purchase, StockOutEvent, ChatMessage
│   ├── routes/                  # dashboard, inventory, purchase, chat,
│   │                             # upload, suppliers, insights blueprints
│   ├── services/
│   │   ├── analytics.py         # health score, profit leak, dead stock,
│   │   │                          expiry, combined dashboard payload
│   │   ├── forecasting.py       # demand forecasting + purchase planning
│   │   ├── csv_import.py        # append-only CSV data import (6 file types)
│   │   ├── memory.py            # conversation history load/save
│   │   ├── intent_service.py    # classifies messages into 5 branches +
│   │   │                          visualization-intent detection
│   │   ├── context_builder.py   # assembles business + RAG context by intent
│   │   ├── planner.py           # prioritized recommendation engine
│   │   ├── tool_executor.py     # Gemini/Anthropic API call layer
│   │   ├── conversation_manager.py  # orchestrates the full chat pipeline
│   │   └── visualization_builder.py # generates chart/table/card_grid JSON
│   │                                  for the Insights canvas
│   └── rag/
│       ├── knowledge_documents.py  # seed knowledge base content
│       └── retriever.py            # ChromaDB init + semantic retrieval
├── data/
│   └── seed.py                  # realistic demo data generator
├── templates/                   # dashboard.html, chat.html, insights.html,
│                                   upload.html, suppliers.html, base.html
└── static/
    ├── css/style.css
    └── js/{dashboard,chat,insights,upload}.js
```

## Insights Canvas — AI-generated charts, tables, and cards

Visit `/insights` (or click "📊 Open in Insights" on any business-related
chat reply on the main `/chat` page) for a dedicated visualization
workspace: a narrow chat sidebar on the left, and a dynamic canvas on the
right that renders whatever the AI decides best answers your request —
line/bar charts, data tables, or summary card grids — grounded in real
business data, never invented numbers.

How it works:
- `intent_service.wants_visualization()` detects when a message is asking
  for a chart/table/comparison (keyword-based, no extra LLM call needed
  just to detect this).
- On the main `/chat` page, a business-related message that also wants
  visualization gets an "📊 Open in Insights" button. Clicking it opens
  `/insights` in a new tab and runs that same request there.
- On the Insights page itself, every message both gets a normal
  conversational reply AND triggers a second, focused LLM call
  (`visualization_builder.build_visualization()`) that asks specifically
  for structured JSON — one or more blocks of type `chart`, `table`, or
  `card_grid` — validated against a fixed schema before rendering, so a
  malformed AI response never breaks the page (it just shows nothing to
  display instead of crashing).
- The canvas has manual date-range filter controls too, plus a Refresh
  button to regenerate the last visualization on demand.



Visit `/upload` to import real data via 6 CSV file types (suppliers,
medicines, stock batches, sales, purchases, stock-out events). Import order
matters — see the page for the required order and column format. Uploads are
append-only: nothing existing is ever deleted.

## Notes on the demand forecasting model

`app/services/forecasting.py` uses a weighted moving-average + linear trend
model over each medicine's trailing 60-day sales. The function signatures are
written so a more sophisticated model (Prophet, ARIMA) can be swapped in
later without changing any calling code.
