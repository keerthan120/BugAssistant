from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime
import os
import httpx
import json
from dotenv import load_dotenv

# Load environment variables from the .env file at startup
load_dotenv()

app = FastAPI(title="SoftwareBugAssistant API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── In-Memory Database (Thread-Safe Mocking) ───────────────────────────────
tickets: Dict[str, Any] = {
    "TKT-001": {"id":"TKT-001","title":"Login page crashes on iOS Safari","description":"Users report the login page crashes when using Safari on iOS 16+.","status":"open","priority":"high","assignee":"alice@company.com","created_at":"2026-05-20","updated_at":"2026-05-20","tags":["mobile","login","crash","ios"]},
    "TKT-002": {"id":"TKT-002","title":"API response slow on large datasets","description":"API takes >10s to respond when fetching more than 1000 records.","status":"in-progress","priority":"medium","assignee":"bob@company.com","created_at":"2026-05-21","updated_at":"2026-05-22","tags":["api","performance","timeout"]},
    "TKT-003": {"id":"TKT-003","title":"Dark mode text unreadable","description":"Several text elements are not visible in dark mode due to poor contrast.","status":"open","priority":"low","assignee":"alice@company.com","created_at":"2026-05-22","updated_at":"2026-05-22","tags":["ui","dark-mode","accessibility"]},
    "TKT-004": {"id":"TKT-004","title":"CSV export missing columns","description":"When exporting to CSV, 3 columns (phone, address, notes) are missing.","status":"resolved","priority":"high","assignee":"charlie@company.com","created_at":"2026-05-18","updated_at":"2026-05-23","tags":["export","csv","data"]},
    "TKT-005": {"id":"TKT-005","title":"Notification emails not sending","description":"System emails not delivered. SMTP logs show 550 error from mail server.","status":"open","priority":"critical","assignee":"bob@company.com","created_at":"2026-05-24","updated_at":"2026-05-24","tags":["email","notifications","smtp"]},
    "TKT-006": {"id":"TKT-006","title":"Dashboard charts not loading","description":"Analytics dashboard shows blank charts for users with >10k data points.","status":"in-progress","priority":"high","assignee":"charlie@company.com","created_at":"2026-05-25","updated_at":"2026-05-25","tags":["dashboard","charts","javascript"]},
}

# Session isolation: maps user/session keys to conversation arrays
sessions_db: Dict[str, List[Dict[str, Any]]] = {}

# ── Pydantic Models ────────────────────────────────────────────────────────
class ChatRequest(BaseModel):
    message: str
    api_key: Optional[str] = None  # Handled as optional since backend can use .env instead
    session_id: str = "default-user"

class CreateTicketRequest(BaseModel):
    title: str
    description: str
    priority: str = "medium"
    assignee: str = "unassigned"

class UpdateStatusRequest(BaseModel):
    status: str

class UpdatePriorityRequest(BaseModel):
    priority: str

# ── Tool Implementations ───────────────────────────────────────────────────
def today():
    return datetime.now().strftime("%Y-%m-%d")

def next_ticket_id():
    if not tickets:
        return "TKT-001"
    nums = [int(k.split("-")[1]) for k in tickets.keys() if "-" in k]
    return f"TKT-{(max(nums) + 1):03d}" if nums else "TKT-001"

def tool_create_new_ticket(title: str, description: str, priority: str = "medium", assignee: str = "unassigned"):
    tid = next_ticket_id()
    tickets[tid] = {
        "id": tid, "title": title, "description": description, "status": "open",
        "priority": priority.lower(), "assignee": assignee,
        "created_at": today(), "updated_at": today(), "tags": []
    }
    return {"success": True, "ticket": tickets[tid], "message": f"Ticket {tid} created."}

def tool_get_ticket_by_id(ticket_id: str):
    t = tickets.get(ticket_id.upper())
    return {"success": True, "ticket": t} if t else {"success": False, "message": f"{ticket_id} not found."}

def tool_search_tickets(query: str):
    q = query.lower()
    results = [t for t in tickets.values()
               if q in t["title"].lower() or q in t["description"].lower()
               or any(q in tag for tag in t.get("tags", []))]
    return {"success": True, "count": len(results), "tickets": results}

def tool_get_tickets_by_status(status: str):
    results = [t for t in tickets.values() if t["status"] == status.lower()]
    return {"success": True, "count": len(results), "tickets": results}

def tool_get_tickets_by_priority(priority: str):
    results = [t for t in tickets.values() if t["priority"] == priority.lower()]
    return {"success": True, "count": len(results), "tickets": results}

def tool_get_tickets_by_assignee(assignee: str):
    results = [t for t in tickets.values() if assignee.lower() in t["assignee"].lower()]
    return {"success": True, "count": len(results), "tickets": results}

def tool_get_tickets_by_date_range(start_date: str, end_date: str):
    results = [t for t in tickets.values() if start_date <= t["created_at"] <= end_date]
    return {"success": True, "count": len(results), "tickets": results}

def tool_update_ticket_status(ticket_id: str, new_status: str):
    tid = ticket_id.upper()
    if tid not in tickets:
        return {"success": False, "message": f"{ticket_id} not found."}
    valid = ["open", "in-progress", "resolved", "closed", "pending"]
    if new_status.lower() not in valid:
        return {"success": False, "message": f"Invalid status. Valid: {valid}"}
    tickets[tid]["status"] = new_status.lower()
    tickets[tid]["updated_at"] = today()
    return {"success": True, "message": f"{tid} status -> '{new_status}'", "ticket": tickets[tid]}

def tool_update_ticket_priority(ticket_id: str, new_priority: str):
    tid = ticket_id.upper()
    if tid not in tickets:
        return {"success": False, "message": f"{ticket_id} not found."}
    valid = ["low", "medium", "high", "critical"]
    if new_priority.lower() not in valid:
        return {"success": False, "message": f"Invalid priority. Valid: {valid}"}
    tickets[tid]["priority"] = new_priority.lower()
    tickets[tid]["updated_at"] = today()
    return {"success": True, "message": f"{tid} priority -> '{new_priority}'", "ticket": tickets[tid]}

async def tool_google_search_agent(query: str):
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            r = await client.get(
                f"https://api.duckduckgo.com/?q={query}&format=json&no_html=1&skip_disambig=1"
            )
            d = r.json()
            abstract = d.get("AbstractText", "")
            related = [x.get("Text", "") for x in d.get("RelatedTopics", [])[:4] if "Text" in x]
            return {"success": True, "query": query, "summary": abstract or "No instant answer found.", "related": related}
    except Exception as e:
        return {"success": False, "query": query, "message": str(e)}

# Dynamic clean execution mapper
def execute_local_tool(name: str, args: dict):
    mappers = {
        "create_new_ticket": tool_create_new_ticket,
        "get_ticket_by_id": tool_get_ticket_by_id,
        "search_tickets": tool_search_tickets,
        "get_tickets_by_status": tool_get_tickets_by_status,
        "get_tickets_by_priority": tool_get_tickets_by_priority,
        "get_tickets_by_assignee": tool_get_tickets_by_assignee,
        "get_tickets_by_date_range": tool_get_tickets_by_date_range,
        "update_ticket_status": tool_update_ticket_status,
        "update_ticket_priority": tool_update_ticket_priority,
    }
    if name in mappers:
        try:
            return mappers[name](**args)
        except TypeError as e:
            return {"error": f"Invalid argument properties passed to {name}: {str(e)}"}
    return {"error": f"Unknown tool: {name}"}

TOOLS_SCHEMA = [
    {"type":"function","function":{"name":"create_new_ticket","description":"Create a new bug/issue ticket","parameters":{"type":"object","properties":{"title":{"type":"string"},"description":{"type":"string"},"priority":{"type":"string","enum":["low","medium","high","critical"]},"assignee":{"type":"string"}},"required":["title","description"]}}},
    {"type":"function","function":{"name":"get_ticket_by_id","description":"Get ticket by ID (e.g. TKT-001)","parameters":{"type":"object","properties":{"ticket_id":{"type":"string"}},"required":["ticket_id"]}}},
    {"type":"function","function":{"name":"search_tickets","description":"Search tickets by keyword","parameters":{"type":"object","properties":{"query":{"type":"string"}},"required":["query"]}}},
    {"type":"function","function":{"name":"get_tickets_by_status","description":"Get tickets by status","parameters":{"type":"object","properties":{"status":{"type":"string","enum":["open","in-progress","resolved","closed","pending"]}},"required":["status"]}}},
    {"type":"function","function":{"name":"get_tickets_by_priority","description":"Get tickets by priority","parameters":{"type":"object","properties":{"priority":{"type":"string","enum":["low","medium","high","critical"]}},"required":["priority"]}}},
    {"type":"function","function":{"name":"get_tickets_by_assignee","description":"Get tickets by assignee","parameters":{"type":"object","properties":{"assignee":{"type":"string"}},"required":["assignee"]}}},
    {"type":"function","function":{"name":"get_tickets_by_date_range","description":"Get tickets in date range (YYYY-MM-DD)","parameters":{"type":"object","properties":{"start_date":{"type":"string"},"end_date":{"type":"string"}},"required":["start_date","end_date"]}}},
    {"type":"function","function":{"name":"update_ticket_status","description":"Update ticket status","parameters":{"type":"object","properties":{"ticket_id":{"type":"string"},"new_status":{"type":"string","enum":["open","in-progress","resolved","closed","pending"]}},"required":["ticket_id","new_status"]}}},
    {"type":"function","function":{"name":"update_ticket_priority","description":"Update ticket priority","parameters":{"type":"object","properties":{"ticket_id":{"type":"string"},"new_priority":{"type":"string","enum":["low","medium","high","critical"]}},"required":["ticket_id","new_priority"]}}},
    {"type":"function","function":{"name":"google_search_agent","description":"Search web for bug/error info","parameters":{"type":"object","properties":{"query":{"type":"string"}},"required":["query"]}}},
]

SYSTEM_PROMPT = """You are SoftwareBugAssistant, an expert AI agent for IT Support and Software Developer teams.
Help triage, manage, and resolve software issues using the ticket management system.
Always use tools to fetch real data. Give clear, structured summaries after tool results.
Today's date: 2026-05-26."""

# ── Agent Loop ─────────────────────────────────────────────────────────────
async def run_agent(user_message: str, fallback_key: Optional[str], session_id: str):
    # Prioritize Key in .env file, then look at what the frontend request passed down
    active_api_key = os.getenv("OPENROUTER_API_KEY") or fallback_key
    
    if not active_api_key:
        raise HTTPException(
            status_code=400, 
            detail="API Key missing. Add 'OPENROUTER_API_KEY' to your .env file or input it in the UI header."
        )

    if session_id not in sessions_db:
        sessions_db[session_id] = []
    
    history = sessions_db[session_id]
    
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        *history[-20:],
        {"role": "user", "content": user_message}
    ]
    used_tools = []

    async with httpx.AsyncClient(timeout=60) as client:
        for _ in range(6):
            resp = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {active_api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://bugassistant.app",
                    "X-Title": "SoftwareBugAssistant",
                },
                json={
                    "model": "meta-llama/llama-3.3-70b-instruct",
                    "messages": messages,
                    "tools": TOOLS_SCHEMA,
                    "tool_choice": "auto",
                    "temperature": 0.1,
                    "max_tokens": 2048,
                }
            )
            if resp.status_code != 200:
                raise HTTPException(status_code=resp.status_code, detail=resp.text[:300])

            data = resp.json()
            choice = data["choices"][0]
            msg = choice["message"]
            
            # Save message sequence cleanly to conversation context tracking 
            messages.append(msg)

            # Check if model wants to call tool paths
            if msg.get("tool_calls"):
                for tc in msg["tool_calls"]:
                    fn_name = tc["function"]["name"]
                    fn_args = json.loads(tc["function"]["arguments"])
                    used_tools.append({"tool": fn_name, "args": fn_args})

                    if fn_name == "google_search_agent":
                        result = await tool_google_search_agent(fn_args.get("query", ""))
                    else:
                        result = execute_local_tool(fn_name, fn_args)

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "name": fn_name,
                        "content": json.dumps(result, default=str)
                    })
            else:
                content = msg.get("content", "Sorry, I could not process that.")
                # Save execution back to persistent isolated user session history
                history.append({"role": "user", "content": user_message})
                history.append({"role": "assistant", "content": content})
                sessions_db[session_id] = history[-20:] # Keep window bound
                
                return {"response": content, "tools_used": used_tools}

    return {"response": "Reached max iterations. Please try a more specific request.", "tools_used": used_tools}

# ── REST Endpoints ─────────────────────────────────────────────────────────

@app.get("/")
def root():
    return {"status": "ok", "message": "SoftwareBugAssistant API running"}

@app.post("/api/chat")
async def chat(req: ChatRequest):
    return await run_agent(req.message, req.api_key, req.session_id)

@app.get("/api/tickets")
def get_all_tickets():
    return {"tickets": list(tickets.values())}

@app.post("/api/tickets")
def create_ticket(req: CreateTicketRequest):
    return tool_create_new_ticket(req.title, req.description, req.priority, req.assignee)

@app.get("/api/tickets/{ticket_id}")
def get_ticket(ticket_id: str):
    t = tickets.get(ticket_id.upper())
    if not t:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return t

@app.put("/api/tickets/{ticket_id}/status")
def update_status(ticket_id: str, req: UpdateStatusRequest):
    return tool_update_ticket_status(ticket_id, req.status)

@app.put("/api/tickets/{ticket_id}/priority")
def update_priority(ticket_id: str, req: UpdatePriorityRequest):
    return tool_update_ticket_priority(ticket_id, req.priority)

@app.delete("/api/tickets/{ticket_id}")
def delete_ticket(ticket_id: str):
    tid = ticket_id.upper()
    if tid not in tickets:
        raise HTTPException(status_code=404, detail="Ticket not found")
    del tickets[tid]
    return {"success": True, "message": f"{tid} deleted."}

@app.get("/api/stats")
def get_stats():
    all_t = list(tickets.values())
    return {
        "total": len(all_t),
        "open": sum(1 for t in all_t if t["status"] == "open"),
        "in_progress": sum(1 for t in all_t if t["status"] == "in-progress"),
        "resolved": sum(1 for t in all_t if t["status"] == "resolved"),
        "critical": sum(1 for t in all_t if t["priority"] == "critical"),
    }