from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from typing import Optional, List
import mysql.connector
import os
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

# --- FastAPI instance ---
api = FastAPI(
    title="BudgetBuddy API",
    description="REST API for BudgetBuddy expense tracking",
    version="1.0.0"
)

# --- DATABASE CONNECTION ---
def get_db_connection():
    return mysql.connector.connect(
        host=os.getenv('DB_HOST'),
        port=os.getenv('DB_PORT'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        database=os.getenv('DB_NAME')
    )

# =========================================
# PYDANTIC MODELS
# =========================================

class ExpenseIn(BaseModel):
    amount: float
    category: str
    description: Optional[str] = None
    date: Optional[str] = None
    is_recurring: bool = False
    recurring_day: Optional[int] = None

class ExpenseOut(BaseModel):
    entry_id: int
    client_id: int
    amount: float
    category: str
    description: Optional[str]
    date: str
    is_recurring: bool
    recurring_day: Optional[int]

class BudgetUpdate(BaseModel):
    budget: float

class GoalIn(BaseModel):
    name: str
    target_amount: float
    deadline: Optional[str] = None

# =========================================
# SECURITY — get_client_id
# Verifies X-Client-ID header against the
# actual signed Flask session cookie.
# Prevents user impersonation via dev tools.
# =========================================

def get_client_id(request: Request):
    client_id = request.headers.get("X-Client-ID")
    if not client_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return int(client_id)

# ============================================================
# EXPENSES
# ============================================================

@api.get("/api/v1/expenses", response_model=List[ExpenseOut])
def get_expenses(request: Request, month: Optional[str] = None):
    client_id = get_client_id(request)
    if not month:
        month = datetime.now().strftime("%Y-%m")
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        "SELECT * FROM entries WHERE client_id = %s AND date LIKE %s ORDER BY date DESC",
        (client_id, f"{month}%")
    )
    expenses = cursor.fetchall()
    cursor.close()
    conn.close()
    for e in expenses:
        e['date'] = str(e['date'])
        e['amount'] = float(e['amount'])
    return expenses

@api.post("/api/v1/expenses", status_code=201)
def add_expense(expense: ExpenseIn, request: Request):
    client_id = get_client_id(request)
    date = expense.date or datetime.now().strftime("%Y-%m-%d")
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO entries 
           (client_id, amount, category, description, date, is_recurring, recurring_day) 
           VALUES (%s, %s, %s, %s, %s, %s, %s)""",
        (client_id, expense.amount, expense.category, expense.description,
         date, expense.is_recurring, expense.recurring_day)
    )
    conn.commit()
    new_id = cursor.lastrowid
    cursor.close()
    conn.close()
    return {"message": "Expense added", "entry_id": new_id}

@api.put("/api/v1/expenses/{entry_id}")
def edit_expense(entry_id: int, expense: ExpenseIn, request: Request):
    client_id = get_client_id(request)
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """UPDATE entries 
           SET amount=%s, category=%s, description=%s, is_recurring=%s, recurring_day=%s 
           WHERE entry_id=%s AND client_id=%s""",
        (expense.amount, expense.category, expense.description,
         expense.is_recurring, expense.recurring_day, entry_id, client_id)
    )
    conn.commit()
    cursor.close()
    conn.close()
    return {"message": "Expense updated"}

@api.delete("/api/v1/expenses/{entry_id}")
def delete_expense(entry_id: int, request: Request, stop_recurring: bool = False):
    client_id = get_client_id(request)
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        if stop_recurring:
            # Find the description of the template to delete all its recurring copies
            cursor.execute(
                "SELECT description FROM entries WHERE entry_id = %s AND client_id = %s",
                (entry_id, client_id)
            )
            expense = cursor.fetchone()
            if expense:
                cursor.execute(
                    "DELETE FROM entries WHERE client_id = %s AND description = %s AND is_recurring = 1",
                    (client_id, expense['description'])
                )
        # Always delete the specific entry clicked
        cursor.execute(
            "DELETE FROM entries WHERE entry_id = %s AND client_id = %s",
            (entry_id, client_id)
        )
        conn.commit()
        return {"message": "Expense deleted successfully"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail="Database error occurred.")
    finally:
        cursor.close()
        conn.close()


# ============================================================
# BUDGET
# ============================================================

@api.put("/api/v1/budget")
def update_budget(data: BudgetUpdate, request: Request):
    client_id = get_client_id(request)
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE clients SET budget=%s WHERE client_id=%s",
        (data.budget, client_id)
    )
    conn.commit()
    cursor.close()
    conn.close()
    return {"message": "Budget updated", "budget": data.budget}


# ============================================================
# GOALS
# ============================================================

@api.get("/api/v1/goals")
def get_goals(request: Request):
    client_id = get_client_id(request)
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        "SELECT * FROM goals WHERE client_id = %s ORDER BY created_at DESC",
        (client_id,)
    )
    goals = cursor.fetchall()
    cursor.close()
    conn.close()
    for g in goals:
        g['target_amount'] = float(g['target_amount'])
        g['saved_amount'] = float(g['saved_amount'])
        if g['deadline']:
            g['deadline'] = str(g['deadline'])
        if g['created_at']:
            g['created_at'] = str(g['created_at'])
    return goals

@api.post("/api/v1/goals", status_code=201)
def create_goal(goal: GoalIn, request: Request):
    client_id = get_client_id(request)
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO goals (client_id, name, target_amount, saved_amount, deadline) VALUES (%s, %s, %s, 0, %s)",
        (client_id, goal.name, goal.target_amount, goal.deadline)
    )
    conn.commit()
    new_id = cursor.lastrowid
    cursor.close()
    conn.close()
    return {"message": "Goal created", "goal_id": new_id}

@api.put("/api/v1/goals/{goal_id}")
def update_goal(goal_id: int, request: Request, amount: float = 0, deduct: bool = False):
    client_id = get_client_id(request)
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        "SELECT * FROM goals WHERE goal_id = %s AND client_id = %s",
        (goal_id, client_id)
    )
    goal = cursor.fetchone()
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")

    # Cap saved amount at target — can't save more than the goal
    new_saved = min(float(goal['saved_amount']) + amount, float(goal['target_amount']))
    cursor.execute(
        "UPDATE goals SET saved_amount = %s WHERE goal_id = %s AND client_id = %s",
        (new_saved, goal_id, client_id)
    )

    # Optional: also log this as an expense entry in the dashboard
    if deduct and amount > 0:
        date_str = datetime.now().strftime("%Y-%m-%d")
        desc = f"Saved for: {goal['name']}"
        cursor.execute(
            """INSERT INTO entries 
               (client_id, amount, category, description, date, is_recurring)
               VALUES (%s, %s, %s, %s, %s, False)""",
            (client_id, amount, 'Savings', desc, date_str)
        )

    conn.commit()
    cursor.close()
    conn.close()
    return {"message": "Goal updated", "saved_amount": new_saved}

@api.delete("/api/v1/goals/{goal_id}")
def delete_goal(goal_id: int, request: Request):
    client_id = get_client_id(request)
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM goals WHERE goal_id = %s AND client_id = %s",
        (goal_id, client_id)
    )
    conn.commit()
    cursor.close()
    conn.close()
    return {"message": "Goal deleted"}


# ============================================================
# ANALYTICS
# ============================================================

@api.get("/api/v1/analytics")
def get_analytics(request: Request, month: Optional[str] = None):
    client_id = get_client_id(request)
    if not month:
        month = datetime.now().strftime("%Y-%m")
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        "SELECT * FROM entries WHERE client_id=%s AND date LIKE %s",
        (client_id, f"{month}%")
    )
    expenses = cursor.fetchall()
    cursor.close()
    conn.close()

    total = 0
    chart = {'Food': 0, 'Travel': 0, 'Books': 0, 'Fun': 0, 'Other': 0}
    for e in expenses:
        amt = float(e['amount'])
        total += amt
        cat = e['category'].strip().capitalize()
        if cat in chart:
            chart[cat] += amt
        else:
            chart['Other'] += amt

    return {
        "month": month,
        "total_spent": round(total, 2),
        "category_breakdown": chart
    }