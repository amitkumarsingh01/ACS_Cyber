import streamlit as st
import psycopg2
from psycopg2.extras import RealDictCursor
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

EMAIL_HOST = os.getenv("EMAIL_HOST")
EMAIL_PORT = int(os.getenv("EMAIL_PORT"))
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD")
EMAIL_FROM_EMAIL = os.getenv("EMAIL_FROM_EMAIL")
DATABASE_URL = os.getenv("DATABASE_URL")

# PostgreSQL Connection
conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
cur = conn.cursor()

# Task limit per user type
TASK_LIMIT = {
    "Regular": 10,
    "Premium": float('inf'),
    "Restricted": 5
}

# Create tables if not exist
cur.execute("""
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    user_type TEXT NOT NULL
)
""")
cur.execute("""
CREATE TABLE IF NOT EXISTS tasks (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    due_date DATE,
    category TEXT,
    priority TEXT NOT NULL,
    completed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    FOREIGN KEY(user_id) REFERENCES users(id)
)
""")
conn.commit()

# Helper functions
def send_email(to_email, subject, body):
    """Send email notifications."""
    try:
        msg = MIMEMultipart()
        msg["From"] = EMAIL_FROM_EMAIL
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        with smtplib.SMTP_SSL(EMAIL_HOST, EMAIL_PORT) as server:
            server.login(EMAIL_HOST_USER, EMAIL_HOST_PASSWORD)
            server.sendmail(EMAIL_FROM_EMAIL, to_email, msg.as_string())
    except Exception as e:
        st.error(f"Error sending email: {e}")

def execute_query(query, params=()):
    cur.execute(query, params)
    conn.commit()

def fetch_query(query, params=()):
    cur.execute(query, params)
    return cur.fetchall()

def get_task_count(user_id):
    query = "SELECT COUNT(*) FROM tasks WHERE user_id = %s"
    return fetch_query(query, (user_id,))[0]["count"]

def get_categories(user_id):
    query = "SELECT DISTINCT category FROM tasks WHERE user_id = %s"
    return [row["category"] for row in fetch_query(query, (user_id,))]

# Streamlit app
def main():
    st.set_page_config(page_title="Enhanced Task Manager", layout="wide")
    st.sidebar.title("Task Manager")

    if "logged_in" not in st.session_state:
        st.session_state["logged_in"] = False

    if st.session_state["logged_in"]:
        task_dashboard(
            st.session_state["user_id"],
            st.session_state["user_email"],
            st.session_state["user_type"]
        )
    else:
        menu = ["Login", "Signup"]
        choice = st.sidebar.radio("Menu", menu)

        if choice == "Login":
            login_page()
        elif choice == "Signup":
            signup_page()

def login_page():
    st.subheader("Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        query = "SELECT id, email, user_type FROM users WHERE username = %s AND password = %s"
        user = fetch_query(query, (username, password))
        if user:
            user = user[0]
            st.session_state["logged_in"] = True
            st.session_state["user_id"] = user["id"]
            st.session_state["user_email"] = user["email"]
            st.session_state["user_type"] = user["user_type"]
            st.success(f"Welcome back, {username}!")
            st.rerun()
        else:
            st.error("Invalid credentials")

def signup_page():
    st.subheader("Sign Up")
    username = st.text_input("Username")
    email = st.text_input("Email")
    password = st.text_input("Password", type="password")
    user_type = st.selectbox("User Type", ["Premium", "Regular", "Restricted"])
    if st.button("Sign Up"):
        try:
            query = "INSERT INTO users (username, email, password, user_type) VALUES (%s, %s, %s, %s)"
            execute_query(query, (username, email, password, user_type))
            send_email(email, "Welcome to Task Manager", "Your account has been created successfully!")
            st.success("Signup successful! Please login.")
        except Exception as e:
            st.error(f"Signup failed: {e}")

def task_dashboard(user_id, user_email, user_type):
    st.sidebar.header("Dashboard")
    if st.sidebar.button("Logout"):
        st.session_state["logged_in"] = False
        st.rerun()

    task_limit = TASK_LIMIT[user_type]
    current_task_count = get_task_count(user_id)

    tab1, tab2, tab3 = st.tabs(["View Tasks", "Add Task", "Statistics"])

    # Tab 1: View Tasks
    with tab1:
        st.subheader("Your Tasks")
        category_filter = st.selectbox("Filter by Category", ["All"] + get_categories(user_id))
        filter_option = st.selectbox("Filter by Status", ["All", "Completed", "Uncompleted"])

        query = "SELECT * FROM tasks WHERE user_id = %s"
        params = [user_id]
        if category_filter != "All":
            query += " AND category = %s"
            params.append(category_filter)
        if filter_option != "All":
            query += " AND completed = %s"
            params.append(True if filter_option == "Completed" else False)

        tasks = fetch_query(query, params)
        if tasks:
            for task in tasks:
                st.write(task)
        else:
            st.info("No tasks to display.")

    # Tab 2: Add Task
    with tab2:
        st.subheader("Add New Task")
        if current_task_count >= task_limit:
            st.error(f"Task limit of {task_limit} reached. Upgrade to add more tasks.")
        else:
            title = st.text_input("Title")
            description = st.text_area("Description")
            due_date = st.date_input("Due Date")
            category = st.text_input("Category")
            priority = st.selectbox("Priority", ["Low", "Medium", "High"])
            if st.button("Add Task"):
                query = """
                INSERT INTO tasks (user_id, title, description, due_date, category, priority) 
                VALUES (%s, %s, %s, %s, %s, %s)
                """
                execute_query(query, (user_id, title, description, due_date, category, priority))
                send_email(user_email, "New Task Added", f"Your task '{title}' was added successfully.")
                st.success("Task added successfully!")
                st.rerun()

    # Tab 3: Statistics
    with tab3:
        st.subheader("Task Statistics")
        completed = fetch_query("SELECT COUNT(*) FROM tasks WHERE user_id = %s AND completed = TRUE", (user_id,))[0]["count"]
        uncompleted = fetch_query("SELECT COUNT(*) FROM tasks WHERE user_id = %s AND completed = FALSE", (user_id,))[0]["count"]
        st.metric("Completed Tasks", completed)
        st.metric("Uncompleted Tasks", uncompleted)

if __name__ == "__main__":
    main()
