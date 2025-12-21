import os
import random
import calendar
import requests
import json
import mysql.connector
import sys
from datetime import datetime
from itertools import groupby

# --- 1. IMPORTS ---
from dotenv import load_dotenv
from flask import Flask, render_template, url_for, session, redirect, request, jsonify, make_response
from oauthlib.oauth2 import WebApplicationClient
from werkzeug.security import generate_password_hash, check_password_hash

# --- 2. LOAD SECRETS ---
load_dotenv()

# --- 3. CONFIGURATION ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_DIR = os.path.join(BASE_DIR, 'templates')
STATIC_DIR = os.path.join(BASE_DIR, 'static')

app = Flask(__name__, template_folder=TEMPLATE_DIR, static_folder=STATIC_DIR)
app.secret_key = os.getenv('SECRET_KEY', 'default_secret_key')

# Force Insecure Transport (Localhost testing)
if os.getenv('OAUTHLIB_INSECURE_TRANSPORT'):
    os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = os.getenv('OAUTHLIB_INSECURE_TRANSPORT')

# --- 4. DATABASE CONNECTION ---
def get_db_connection():
    return mysql.connector.connect(
        # These names must match the "Keys" you enter in Render's dashboard
        host=os.getenv('DB_HOST'),
        port=os.getenv('DB_PORT'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        database=os.getenv('DB_NAME')
    )

# --- 5. GOOGLE SETUP ---
GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID')
GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET')
GOOGLE_DISCOVERY_URL = "https://accounts.google.com/.well-known/openid-configuration"
client = WebApplicationClient(GOOGLE_CLIENT_ID)

# --- 6. EMAIL SETUP (BREVO API) ---
# We use this helper instead of flask-mail to bypass blocked ports on free hosting
def send_email_http(to_email, subject, body):
    url = "https://api.brevo.com/v3/smtp/email"
    
    payload = json.dumps({
        "sender": {"name": "BudgetBuddy", "email": os.getenv('SENDER_EMAIL')},
        "to": [{"email": to_email}],
        "subject": subject,
        "htmlContent": f"<p>{body}</p>"
    })
    
    headers = {
        'accept': 'application/json',
        'api-key': os.getenv('BREVO_API_KEY'),
        'content-type': 'application/json'
    }
    
    try:
        response = requests.post(url, headers=headers, data=payload)
        # Check if status code is 201 (Created) or 200 (OK)
        return response.status_code in [200, 201]
    except Exception as e:
        print(f"Email Error: {e}", file=sys.stderr)
        return False

# --- 7. HELPER FUNCTIONS ---
def find_user_by_email(email):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM clients WHERE email = %s", (email,))
    user = cursor.fetchone()
    cursor.close()
    conn.close()
    return user

def get_analytics(client_id, target_date=None):
    if not target_date: target_date = datetime.now().strftime("%Y-%m")
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    query = "SELECT * FROM entries WHERE client_id = %s AND date LIKE %s"
    cursor.execute(query, (client_id, f"{target_date}%"))
    expenses = cursor.fetchall()
    
    cursor.close()
    conn.close()

    total_spent = 0
    chart_data = {'food':0, 'travel':0, 'books':0, 'fun':0, 'other':0}

    for row in expenses:
        amt = float(row['amount'])
        total_spent += amt
        cat = row['category'].lower()
        if cat in chart_data: chart_data[cat] += amt
        else: chart_data['other'] += amt
            
    return expenses, total_spent, list(chart_data.values())

# --- 8. ROUTES ---

@app.route('/')
def home(): return render_template('login.html')

# --- OTP & REGISTER ---
@app.route('/send_otp', methods=['POST'])
def send_otp():
    email = request.form.get('email')
    if find_user_by_email(email): return "⚠️ Account exists! Please Log In."
    
    otp = str(random.randint(100000, 999999))
    session['temp_otp'] = otp
    session['temp_email'] = email
    
    # SEND EMAIL VIA BREVO API
    success = send_email_http(
        to_email=email, 
        subject="BudgetBuddy Verification Code", 
        body=f"Your Verification Code is: <strong>{otp}</strong>"
    )
    
    if success:
        return render_template('verify_otp.html', email=email)
    else:
        return "❌ Failed to send email (Check API Key or Server Logs)."

@app.route('/verify_otp', methods=['POST'])
def verify_otp():
    if request.form.get('otp', '').strip() == str(session.get('temp_otp', '')).strip():
        return render_template('setup_profile.html', email=session['temp_email'])
    return "❌ Wrong OTP!"

@app.route('/save_profile', methods=['POST'])
def save_profile():
    email = request.form.get('email')
    if find_user_by_email(email): return redirect(url_for('home'))
    
    name = request.form.get('name')
    password = request.form.get('password')
    hashed_pw = generate_password_hash(password) 
    pic = "https://ui-avatars.com/api/?name=" + name + "&background=random"

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO clients (name, email, profile_pic, password, budget) VALUES (%s, %s, %s, %s, %s)",
        (name, email, pic, hashed_pw, 15000)
    )
    conn.commit()
    
    client_id = cursor.lastrowid
    cursor.close()
    conn.close()
    
    session['user'] = {'name': name, 'email': email, 'given_name': name.split()[0], 'picture': pic}
    session['client_id'] = client_id
    return redirect(url_for('dashboard'))

@app.route('/login_password', methods=['POST'])
def login_password():
    user = find_user_by_email(request.form.get('email'))
    input_pass = request.form.get('password').strip()
    
    if user and check_password_hash(user['password'], input_pass):
        session['user'] = {'name': user['name'], 'email': user['email'], 'given_name': user['name'].split()[0], 'picture': user['profile_pic']}
        session['client_id'] = user['client_id']
        return redirect(url_for('dashboard'))
    return "❌ Login Failed!"

# --- GOOGLE LOGIN ROUTES ---
@app.route("/login/google")
def login_google():
    google_provider_cfg = requests.get(GOOGLE_DISCOVERY_URL).json()
    
    # Dynamic redirect URI based on environment
    redirect_uri = "http://127.0.0.1:5000/authorize/google"
    if os.getenv('MYSQL_HOST') and 'pythonanywhere' in os.getenv('MYSQL_HOST'):
        # Construct the live URL dynamically
        base_url = "https://" + os.environ.get('MYSQL_HOST').split('.')[0] + ".pythonanywhere.com"
        redirect_uri = base_url + "/authorize/google"

    request_uri = client.prepare_request_uri(
        google_provider_cfg["authorization_endpoint"],
        redirect_uri=redirect_uri,
        scope=["openid", "email", "profile"],
    )
    return redirect(request_uri)

@app.route("/authorize/google")
def callback():
    code = request.args.get("code")
    google_provider_cfg = requests.get(GOOGLE_DISCOVERY_URL).json()
    
    # Handle both http (local) and https (live) callbacks
    token_url, headers, body = client.prepare_token_request(
        google_provider_cfg["token_endpoint"],
        authorization_response=request.url.replace("http://", "https://") if "pythonanywhere" in request.url else request.url,
        redirect_url=request.base_url.replace("http://", "https://") if "pythonanywhere" in request.base_url else request.base_url,
        code=code
    )
    token_res = requests.post(token_url, headers=headers, data=body, auth=(GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET))
    client.parse_request_body_response(json.dumps(token_res.json()))
    
    uri, headers, body = client.add_token(google_provider_cfg["userinfo_endpoint"])
    userinfo_res = requests.get(uri, headers=headers, data=body).json()
    
    email = userinfo_res.get("email")
    user = find_user_by_email(email)

    if not user:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO clients (google_id, name, email, profile_pic, password, budget) VALUES (%s, %s, %s, %s, %s, %s)",
            (userinfo_res.get("sub"), userinfo_res.get("name"), email, userinfo_res.get("picture"), "google_auth", 15000)
        )
        conn.commit()
        user = find_user_by_email(email)
        cursor.close()
        conn.close()

    session['user'] = {'name': user['name'], 'email': user['email'], 'given_name': user['name'].split()[0], 'picture': user['profile_pic']}
    session['client_id'] = user['client_id']
    return redirect(url_for('dashboard'))

# --- MAIN APP ROUTES ---
@app.route('/dashboard')
def dashboard():
    if 'client_id' not in session: return redirect(url_for('home'))
    cid = session['client_id']
    
    _, m_spent, m_chart = get_analytics(cid, datetime.now().strftime("%Y-%m"))
    expenses, d_spent, _ = get_analytics(cid, datetime.now().strftime("%Y-%m-%d"))
    
    user = find_user_by_email(session['user']['email'])
    budget = float(user['budget']) if user else 15000
    
    days_in_month = calendar.monthrange(datetime.now().year, datetime.now().month)[1]
    days_left = days_in_month - datetime.now().day + 1
    
    data = {
        "budget": int(budget), "balance": int(budget - m_spent), 
        "daily_limit": int((budget - m_spent)/days_left) if days_left > 0 else 0, 
        "spent_today": int(d_spent), "currency": "₹", "chart_data": m_chart
    }
    
    response = make_response(render_template('dashboard.html', user=session['user'], data=data, transactions=expenses))
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return response

@app.route('/reports')
def reports():
    if 'client_id' not in session: return redirect(url_for('home'))
    selected_month = request.args.get('month') or datetime.now().strftime("%Y-%m")
    
    expenses, total_spent, _ = get_analytics(session['client_id'], selected_month)
    
    categories = ['Food', 'Travel', 'Fun', 'Books', 'Other']
    chart_totals = {cat: 0 for cat in categories}

    for row in expenses:
        cat = row['category'].strip().capitalize()
        amt = float(row['amount'])
        if cat in chart_totals: chart_totals[cat] += amt
        else: chart_totals['Other'] += amt

    now = datetime.now()
    if selected_month == now.strftime("%Y-%m"): days_passed = now.day
    else: days_passed = calendar.monthrange(int(selected_month[:4]), int(selected_month[5:]))[1]
    
    average_spent = int(total_spent / days_passed) if days_passed > 0 else 0

    expenses.sort(key=lambda x: str(x['date']), reverse=True)
    daily_grouped = []
    for date, items in groupby(expenses, key=lambda x: str(x['date'])):
        daily_grouped.append((date, list(items)))

    r = {
        'selected_month': selected_month, 'total': int(total_spent),
        'average': average_spent, 'categories': categories,
        'cat_values': list(chart_totals.values()), 'daily_grouped': daily_grouped
    }
    return render_template('reports.html', user=session['user'], r=r)

@app.route('/add_expense', methods=['POST'])
def add_expense():
    if 'client_id' not in session: return redirect(url_for('home'))
    date = request.form.get('date') or datetime.now().strftime("%Y-%m-%d")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO entries (client_id, amount, category, description, date) VALUES (%s, %s, %s, %s, %s)",
        (session['client_id'], request.form.get('amount'), request.form.get('category'), request.form.get('description'), date)
    )
    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for('dashboard'))

@app.route('/edit_transaction', methods=['POST'])
def edit_transaction():
    if 'client_id' not in session: return redirect(url_for('home'))
    
    t_id = request.form.get('id')
    desc = request.form.get('description')
    amt = request.form.get('amount')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("UPDATE entries SET description = %s, amount = %s WHERE entry_id = %s AND client_id = %s", 
                       (desc, amt, t_id, session['client_id']))
        conn.commit()
    except mysql.connector.Error as err:
        print("Error: ", err)
    finally:
        cursor.close()
        conn.close()
        
    return redirect(url_for('dashboard'))

@app.route('/update_budget', methods=['POST'])
def update_budget():
    if 'client_id' not in session: return redirect(url_for('home'))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE clients SET budget = %s WHERE client_id = %s", (request.form.get('budget'), session['client_id']))
    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for('dashboard'))

@app.route('/update_budget_incremental', methods=['POST'])
def update_budget_incremental():
    if 'client_id' not in session: return redirect(url_for('home'))
    
    action = request.form.get('action')
    try:
        amount = float(request.form.get('amount'))
    except:
        return redirect(url_for('dashboard'))
        
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("SELECT budget FROM clients WHERE client_id = %s", (session['client_id'],))
    result = cursor.fetchone()
    current_budget = float(result['budget']) if result else 0
    
    if action == 'add':
        new_budget = current_budget + amount
    elif action == 'sub':
        new_budget = current_budget - amount
    else:
        new_budget = current_budget
        
    cursor.execute("UPDATE clients SET budget = %s WHERE client_id = %s", (new_budget, session['client_id']))
    conn.commit()
    cursor.close()
    conn.close()
    
    return redirect(url_for('dashboard'))

# --- SETTINGS ROUTES ---

@app.route('/settings')
def settings():
    if 'client_id' not in session:
        return redirect(url_for('home')) 
    
    user_db = find_user_by_email(session['user']['email'])
    
    if not user_db:
        return redirect(url_for('home'))

    is_google_user = (user_db['password'] == 'google_auth')
    
    session['user']['name'] = user_db['name']
    session['user']['picture'] = user_db['profile_pic']

    return render_template('settings.html', user=session['user'], is_google_user=is_google_user)

@app.route('/update_settings', methods=['POST'])
def update_settings():
    if 'client_id' not in session: return redirect(url_for('home'))
    
    new_name = request.form.get('name')
    new_pic = request.form.get('profile_pic')
    new_pass = request.form.get('password')
    client_id = session['client_id']
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if new_pass and new_pass.strip():
        hashed_pw = generate_password_hash(new_pass)
        cursor.execute("UPDATE clients SET name = %s, profile_pic = %s, password = %s WHERE client_id = %s", 
                       (new_name, new_pic, hashed_pw, client_id))
    else:
        cursor.execute("UPDATE clients SET name = %s, profile_pic = %s WHERE client_id = %s", 
                       (new_name, new_pic, client_id))
        
    conn.commit()
    cursor.close()
    conn.close()
    
    session['user']['name'] = new_name
    session['user']['given_name'] = new_name.split()[0]
    session['user']['picture'] = new_pic
    session.modified = True
    
    return redirect(url_for('dashboard'))

@app.route('/change_password', methods=['POST'])
def change_password():
    if 'client_id' not in session:
        return jsonify({'success': False, 'message': 'Session expired. Please login again.'})

    data = request.get_json()
    old_pass = data.get('old_password')
    new_pass = data.get('new_password')
    client_id = session['client_id']

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM clients WHERE client_id = %s", (client_id,))
    user = cursor.fetchone()

    # 1. VERIFY OLD PASSWORD
    if not check_password_hash(user['password'], old_pass):
        cursor.close()
        conn.close()
        return jsonify({'success': False, 'message': '❌ Incorrect Old Password! Please try again.'})

    # 2. UPDATE NEW PASSWORD
    hashed_pw = generate_password_hash(new_pass)
    cursor.execute("UPDATE clients SET password = %s WHERE client_id = %s", (hashed_pw, client_id))
    conn.commit()
    cursor.close()
    conn.close()

    # 3. SEND EMAIL NOTIFICATION (VIA BREVO)
    send_email_http(
        to_email=user['email'], 
        subject="Security Alert: Password Changed", 
        body=f"Hello {user['name']},\n\nYour BudgetBuddy password was successfully changed just now.\n\nIf this wasn't you, please contact support."
    )

    return jsonify({'success': True, 'message': '✅ Password Changed Successfully!'})

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

@app.route('/api/chart-data')
def chart_data_api():
    if 'client_id' not in session: return jsonify({'chart': []})
    date = request.args.get('date')
    _, _, chart = get_analytics(session['client_id'], date)
    return jsonify({'chart': chart})

if __name__ == '__main__':

    app.run(port=5000, debug=True)
