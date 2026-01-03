"""
Personal Database Assistant
A flexible LLM-powered app for tracking anything: energy, journals, finances, habits, etc.
Deploy to Railway/Render and access from any device.
"""

import json
import sqlite3
from datetime import datetime
from openai import OpenAI
import gradio as gr

# Initialize
client = OpenAI()  # Set OPENAI_API_KEY env var
DB_PATH = "personal.db"

def get_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row  # Enable column access by name
    return conn

conn = get_connection()

# =============================================================================
# SYSTEM PROMPT - The brain of the operation
# =============================================================================

SYSTEM_PROMPT = """You are a personal database assistant. You help the user track anything they want: energy levels, journals, finances, habits, goals, books, workouts—anything.

## Your Capabilities
You have two tools:
1. `inspect_schema` - See all existing tables and their structures. Use this FIRST when the user mentions something that might already exist, or to understand what's available.
2. `execute_sql` - Run any SQL (CREATE, INSERT, SELECT, UPDATE, DELETE). Use this to create tables, add data, query data, and generate insights.

## How to Behave

### When the user wants to track something new:
1. First, use `inspect_schema` to check if a similar table exists
2. Propose a schema design BEFORE creating it. Explain your thinking:
   - What columns would be useful?
   - What data types make sense?
   - Should it relate to existing tables?
3. Ask if they want any modifications
4. Only create the table after they approve (or if they say "just do it" / seem to want you to decide)

### When the user logs an entry:
1. Parse their natural language into structured data
2. If anything is ambiguous, make reasonable assumptions but mention them
3. Insert the data and confirm what you stored
4. Use the current date/time if not specified

### When the user asks for insights:
1. Query the relevant data
2. Provide clear summaries with actual numbers
3. Look for patterns, trends, correlations
4. If they ask about relationships between different trackers, JOIN across tables
5. Suggest visualizations when appropriate (describe what a chart would show)

### General Guidelines:
- Be conversational and warm, not robotic
- Use `inspect_schema` liberally—it's cheap and keeps you oriented
- When creating tables, always include: `id INTEGER PRIMARY KEY AUTOINCREMENT`, `created_at TEXT DEFAULT CURRENT_TIMESTAMP`
- For dates, use TEXT in ISO format (SQLite-friendly)
- For flexible tagging/notes, a TEXT field works great
- If they seem frustrated or confused, ask clarifying questions
- Remember: you can see conversation history, so reference previous context

## Current Date/Time
Right now it's: {current_time}
"""

# =============================================================================
# TOOLS
# =============================================================================

tools = [
    {
        "type": "function",
        "function": {
            "name": "inspect_schema",
            "description": "Get the current database schema: all tables, their columns, types, and sample row counts. Use this to understand what tracking systems exist before creating new ones or querying data.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "execute_sql",
            "description": "Execute a SQL statement on the database. Use for CREATE TABLE, INSERT, SELECT, UPDATE, DELETE operations.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sql": {
                        "type": "string",
                        "description": "The SQL statement to execute"
                    },
                    "operation_type": {
                        "type": "string",
                        "enum": ["read", "write"],
                        "description": "Whether this is a read (SELECT) or write (INSERT/UPDATE/DELETE/CREATE) operation"
                    },
                    "explanation": {
                        "type": "string",
                        "description": "Brief explanation of what this query does (for the user)"
                    }
                },
                "required": ["sql", "operation_type", "explanation"]
            }
        }
    }
]

def inspect_schema():
    """Returns a formatted view of all tables and their structures."""
    cursor = conn.cursor()
    
    # Get all tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = cursor.fetchall()
    
    if not tables:
        return "📭 Database is empty. No tables exist yet."
    
    schema_info = []
    for (table_name,) in tables:
        # Get column info
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = cursor.fetchall()
        col_descriptions = [f"  - {col[1]} ({col[2]})" for col in columns]
        
        # Get row count
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        count = cursor.fetchone()[0]
        
        # Get sample of recent entries
        cursor.execute(f"SELECT * FROM {table_name} ORDER BY ROWID DESC LIMIT 2")
        samples = cursor.fetchall()
        
        table_info = f"📊 **{table_name}** ({count} rows)\n"
        table_info += "\n".join(col_descriptions)
        
        if samples:
            table_info += f"\n  Recent entries: {len(samples)} shown"
            for sample in samples:
                # Convert Row to dict for readable display
                sample_dict = dict(sample)
                # Truncate long values
                for k, v in sample_dict.items():
                    if isinstance(v, str) and len(v) > 50:
                        sample_dict[k] = v[:50] + "..."
                table_info += f"\n    → {sample_dict}"
        
        schema_info.append(table_info)
    
    return "\n\n".join(schema_info)

def execute_sql(sql: str, operation_type: str, explanation: str):
    """Execute SQL and return results."""
    cursor = conn.cursor()
    try:
        cursor.execute(sql)
        
        if operation_type == "read":
            rows = cursor.fetchall()
            if not rows:
                return f"✅ {explanation}\n\nNo results found."
            
            # Format results nicely
            columns = [description[0] for description in cursor.description]
            results = [dict(zip(columns, row)) for row in rows]
            
            # Create a simple text table
            output = f"✅ {explanation}\n\n"
            if len(results) <= 20:
                for row in results:
                    output += f"• {row}\n"
            else:
                for row in results[:10]:
                    output += f"• {row}\n"
                output += f"\n... and {len(results) - 10} more rows"
            
            return output
        else:
            conn.commit()
            affected = cursor.rowcount
            return f"✅ {explanation}\n\nRows affected: {affected if affected >= 0 else 'N/A (schema change)'}"
    
    except Exception as e:
        return f"❌ Error: {e}\n\nSQL attempted: {sql}"

def handle_tool_call(tool_name: str, arguments: dict) -> str:
    """Route tool calls to their implementations."""
    if tool_name == "inspect_schema":
        return inspect_schema()
    elif tool_name == "execute_sql":
        return execute_sql(
            arguments["sql"],
            arguments.get("operation_type", "read"),
            arguments.get("explanation", "Executing query")
        )
    else:
        return f"Unknown tool: {tool_name}"

# =============================================================================
# CHAT LOOP
# =============================================================================

def chat(message: str, history: list) -> str:
    """Main chat function for Gradio."""
    
    # Build messages with current timestamp
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S (%A)")
    system = SYSTEM_PROMPT.format(current_time=current_time)
    
    messages = [{"role": "system", "content": system}]
    
    # Add conversation history
    for user_msg, assistant_msg in history:
        messages.append({"role": "user", "content": user_msg})
        messages.append({"role": "assistant", "content": assistant_msg})
    
    messages.append({"role": "user", "content": message})
    
    # Call the model
    response = client.chat.completions.create(
        model="gpt-4o-mini",  # Good balance of speed/cost/capability
        messages=messages,
        tools=tools,
        tool_choice="auto"
    )
    
    assistant_message = response.choices[0].message
    
    # Handle tool calls in a loop (model might chain multiple calls)
    while assistant_message.tool_calls:
        # Process each tool call
        for tool_call in assistant_message.tool_calls:
            func_name = tool_call.function.name
            func_args = json.loads(tool_call.function.arguments)
            
            result = handle_tool_call(func_name, func_args)
            
            # Add the assistant's tool call and the result to messages
            messages.append({
                "role": "assistant",
                "tool_calls": [tool_call.model_dump()]
            })
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": result
            })
        
        # Get the next response
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            tools=tools,
            tool_choice="auto"
        )
        assistant_message = response.choices[0].message
    
    return assistant_message.content

# =============================================================================
# GRADIO INTERFACE
# =============================================================================

# Custom CSS for a cleaner look
css = """
.gradio-container { max-width: 800px !important; margin: auto; }
footer { display: none !important; }
"""

# Example prompts to help users get started
examples = [
    "I want to start tracking my energy levels",
    "I want to start a daily journal",
    "Help me track my spending",
    "What am I currently tracking?",
    "My energy today is 7/10 - slept well but skipped breakfast",
    "Show me my entries from this week",
    "Any patterns in my data?",
]

with gr.Blocks(css=css, title="Personal Tracker") as app:
    gr.Markdown("# 🗃️ Personal Database Assistant")
    gr.Markdown("Track anything with natural language. I'll handle the database.")
    
    chatbot = gr.ChatInterface(
        fn=chat,
        examples=examples,
        retry_btn=None,
        undo_btn="↩️ Undo",
        clear_btn="🗑️ Clear",
    )

if __name__ == "__main__":
    app.launch(server_name="0.0.0.0", server_port=7860)
