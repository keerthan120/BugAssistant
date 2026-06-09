# 🐛 SoftwareBugAssistant

AI-powered bug triage & ticket management system.
**Backend:** Python (FastAPI) | **Frontend:** HTML + CSS + JavaScript

---

## 📁 File Structure

```
software_bug_assistant/
├── backend/
│   ├── main.py              ← FastAPI server (all tools + OpenRouter agent)
│   └── requirements.txt     ← Python dependencies
├── frontend/
│   └── index.html           ← Full UI (HTML + CSS + JS)
└── README.md
```

---

## ⚙️ Setup & Run

### Step 1 — Open project in VS Code
```
File → Open Folder → select software_bug_assistant
```

### Step 2 — Install Python dependencies
Open terminal (Ctrl + `) and run:
```bash
cd backend
pip install -r requirements.txt
```

### Step 3 — Start the backend
```bash
uvicorn main:app --reload
```
Backend runs at → http://localhost:8000

### Step 4 — Open the frontend
Open a NEW terminal tab:
```bash
cd frontend
```
Then right-click `index.html` → **Open with Live Server**
OR just open the file directly in your browser.

### Step 5 — Add API Key
Paste your OpenRouter API key (https://openrouter.ai) in the header field.

---

## 🔧 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET  | /api/tickets | Get all tickets |
| POST | /api/tickets | Create new ticket |
| GET  | /api/tickets/{id} | Get ticket by ID |
| PUT  | /api/tickets/{id}/status | Update status |
| PUT  | /api/tickets/{id}/priority | Update priority |
| DELETE | /api/tickets/{id} | Delete ticket |
| GET  | /api/stats | Get ticket statistics |
| POST | /api/chat | Chat with LLaMA agent |

---

## 🤖 Agent Tools

| Tool | Description |
|------|-------------|
| create_new_ticket | Create a bug ticket |
| get_ticket_by_id | Lookup TKT-001 etc. |
| search_tickets | Full-text search |
| get_tickets_by_status | Filter by status |
| get_tickets_by_priority | Filter by priority |
| get_tickets_by_assignee | Filter by person |
| get_tickets_by_date_range | Filter by date |
| update_ticket_status | Change status |
| update_ticket_priority | Change priority |
| google_search_agent | Web search (DuckDuckGo) |

---

## 💬 Example Prompts
- "Show all open tickets"
- "List critical bugs"
- "Get details of TKT-005"
- "Mark TKT-002 as resolved"
- "Create a ticket: app crashes on logout"
- "Search for mobile issues"
- "Tickets assigned to alice"
- "Search the web for SMTP 550 error fix"
