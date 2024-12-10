import streamlit as st
import psycopg2
import smtplib
from email.message import EmailMessage
from datetime import datetime, timedelta
import calendar as cal
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

EMAIL_HOST = os.getenv("EMAIL_HOST")
EMAIL_PORT = int(os.getenv("EMAIL_PORT"))
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD")
EMAIL_FROM_EMAIL = os.getenv("EMAIL_FROM_EMAIL")
DATABASE_URL = os.getenv("DATABASE_URL")

# Database setup
conn = psycopg2.connect(DATABASE_URL)
c = conn.cursor()

c.execute("""
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    user_type TEXT NOT NULL
)
""")
c.execute("""
CREATE TABLE IF NOT EXISTS tasks (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    due_date DATE,
    category TEXT,
    priority TEXT NOT NULL,
    completed BOOLEAN DEFAULT FALSE,
    FOREIGN KEY(user_id) REFERENCES users(id)
)
""")
conn.commit()

# Helper functions
def send_email(to_email, subject, body):
    try:
        msg = EmailMessage()
        msg.set_content(body)
        msg["Subject"] = subject
        msg["From"] = EMAIL_FROM_EMAIL
        msg["To"] = to_email

        with smtplib.SMTP_SSL(EMAIL_HOST, EMAIL_PORT) as server:
            server.login(EMAIL_HOST_USER, EMAIL_HOST_PASSWORD)
            server.send_message(msg)
    except Exception as e:
        st.error(f"Error sending email: {e}")

def add_task(user_id, title, description, due_date, category, priority):
    c.execute("""
    INSERT INTO tasks (user_id, title, description, due_date, category, priority) 
    VALUES (%s, %s, %s, %s, %s, %s)
    """, (user_id, title, description, due_date, category, priority))
    conn.commit()

    c.execute("SELECT email FROM users WHERE id = %s", (user_id,))
    user_email = c.fetchone()[0]
    send_email(user_email, "New Task Added", f"Task '{title}' has been added.")

def get_tasks(user_id, filter_by=None, category=None):
    query = "SELECT id, title, description, due_date, category, priority, completed FROM tasks WHERE user_id = %s"
    params = [user_id]
    if filter_by == "completed":
        query += " AND completed = TRUE"
    elif filter_by == "uncompleted":
        query += " AND completed = FALSE"
    if category:
        query += " AND category = %s"
        params.append(category)
    c.execute(query, params)
    return c.fetchall()

def update_task_status(task_id, status):
    c.execute("UPDATE tasks SET completed = %s WHERE id = %s", (status, task_id))
    conn.commit()

    c.execute("SELECT user_id, title FROM tasks WHERE id = %s", (task_id,))
    user_id, title = c.fetchone()
    c.execute("SELECT email FROM users WHERE id = %s", (user_id,))
    user_email = c.fetchone()[0]
    status_text = "completed" if status else "marked as incomplete"
    send_email(user_email, "Task Status Updated", f"Task '{title}' has been {status_text}.")

def update_task(task_id, title, description, due_date, category, priority):
    c.execute("""
    UPDATE tasks SET title = %s, description = %s, due_date = %s, category = %s, priority = %s 
    WHERE id = %s
    """, (title, description, due_date, category, priority, task_id))
    conn.commit()

def delete_task(task_id):
    c.execute("SELECT user_id, title FROM tasks WHERE id = %s", (task_id,))
    user_id, title = c.fetchone()
    c.execute("DELETE FROM tasks WHERE id = %s", (task_id,))
    conn.commit()

    c.execute("SELECT email FROM users WHERE id = %s", (user_id,))
    user_email = c.fetchone()[0]
    send_email(user_email, "Task Deleted", f"Task '{title}' has been deleted.")

def get_task_count(user_id):
    c.execute("SELECT COUNT(*) FROM tasks WHERE user_id = %s", (user_id,))
    return c.fetchone()[0]

def get_categories(user_id):
    c.execute("SELECT DISTINCT category FROM tasks WHERE user_id = %s", (user_id,))
    return [row[0] for row in c.fetchall()]

# Streamlit App
def main():
    st.set_page_config(page_title="Task Manager", page_icon="img.png", layout="wide")
    st.sidebar.image("img.png", width=200)
    st.title("Task Management System")

    if "logged_in" not in st.session_state:
        st.session_state["logged_in"] = False

    if st.session_state["logged_in"]:
        task_dashboard(st.session_state["user_id"], st.session_state["user_type"])
    else:
        menu = ["Login", "Signup"]
        choice = st.sidebar.radio("Menu", menu)

        if choice == "Signup":
            signup_page()
        elif choice == "Login":
            login_page()

def login_page():
    st.subheader("Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        c.execute("SELECT id, user_type FROM users WHERE username = %s AND password = %s", (username, password))
        user = c.fetchone()
        if user:
            st.session_state["logged_in"] = True
            st.session_state["user_id"] = user[0]
            st.session_state["user_type"] = user[1]
            st.success(f"Welcome, {username}!")
            st.rerun()
        else:
            st.error("Invalid credentials. Please try again.")
    if st.button("Forgot Password"):
        with st.form("forgot_password_form", clear_on_submit=True):
            email = st.text_input("Enter your registered email ID")
            if st.form_submit_button("Send Password"):
                c.execute("SELECT password FROM users WHERE email = ?", (email,))
                result = c.fetchone()
                if result:
                    user_password = result[0]
                    send_email(email, "Password Recovery", f"Your password is: {user_password}")
                    st.success(f"Password sent to {email}.")
                else:
                    st.error("Email not found.")

def signup_page():
    st.subheader("Sign Up")
    username = st.text_input("Username")
    email = st.text_input("Email")
    password = st.text_input("Password", type="password")
    user_type = st.selectbox("User Type", ["Premium", "Regular", "Restricted"])
    if st.button("Sign Up"):
        try:
            c.execute("""
            INSERT INTO users (username, email, password, user_type) 
            VALUES (%s, %s, %s, %s)
            """, (username, email, password, user_type))
            conn.commit()
            send_email(email, "Welcome to Task Manager", "Your account has been created successfully!")
            st.success("Account created successfully. Please log in.")
        except psycopg2.IntegrityError:
            st.error("Username or Email already exists.")

def logout():
    st.session_state["logged_in"] = False
    st.session_state["user_id"] = None
    st.session_state["user_type"] = None
    st.success("Logged out successfully!")
    st.rerun()

def task_dashboard(user_id, user_type):
    st.sidebar.title("Dashboard")
    st.sidebar.button("Logout", on_click=logout)
    if st.sidebar.button("Change Password"):
        with st.sidebar.form("change_password_form", clear_on_submit=True):
            old_password = st.text_input("Current Password", type="password")
            new_password = st.text_input("New Password", type="password")
            confirm_password = st.text_input("Confirm Password", type="password")
            if st.form_submit_button("Change Password"):
                c.execute("SELECT password FROM users WHERE id = ?", (user_id,))
                current_password = c.fetchone()[0]
                if old_password == current_password and new_password == confirm_password:
                    c.execute("UPDATE users SET password = ? WHERE id = ?", (new_password, user_id))
                    conn.commit()
                    st.success("Password updated successfully!")
                else:
                    st.error("Invalid credentials or mismatched passwords.")
    if user_type == "Restricted":
        st.sidebar.write("Upgrade to Regular @ ₹29 or Premium @ ₹49")
    elif user_type == "Regular":
        st.sidebar.write("Upgrade to Premium @ ₹49")

    if user_type == "Regular" or user_type == "Restricted":
        task_count = get_task_count(user_id)
        st.sidebar.write(f"Tasks Added: {task_count}/10")
        if task_count >= 10:
            st.error("Task limit reached for Regular users.")

    tab1, tab2, tab3 = st.tabs(["View Tasks", "Add Task", "Statistics"])

    with tab1:
        st.subheader("Your Tasks")
        category_filter = st.selectbox("Filter by Category", ["All"] + get_categories(user_id))
        filter_option = st.selectbox("Filter by Status", ["All", "Completed", "Uncompleted"])
        category = None if category_filter == "All" else category_filter
        filter_by = None if filter_option == "All" else filter_option.lower()

        tasks = get_tasks(user_id, filter_by, category)
        if tasks:
            for task in tasks:
                task_id, title, description, due_date, category, priority, completed = task
                due_date_obj = due_date
                days_left = (due_date_obj - datetime.now().date()).days

                if completed:
                    color = "#00FF00"  # Green for completed
                elif days_left > 7:
                    color = "#FFFF00"  # Yellow for not due soon
                else:
                    color = "#FFA500"  # Orange for due soon

                st.markdown(
                    f"<div style='border-left: 5px solid {color}; padding-left: 10px; margin-bottom: 10px;'>"
                    f"<strong>{title}</strong> ({category}) - Priority: {priority}"
                    f"<br>Due: {due_date} - {'Completed' if completed else 'Not Completed'}"
                    f"<br>{description}</div>", unsafe_allow_html=True
                )

                col1, col2, col3 = st.columns([6, 2, 2])
                with col1:
                    if not completed:
                        if st.button("Mark as Completed", key=f"complete_{task_id}"):
                            update_task_status(task_id, completed=True)
                            st.success("Task marked as completed.")
                            st.rerun()

                with col2:
                    if st.button("Edit", key=f"edit_{task_id}"):
                        with st.form(f"edit_form_{task_id}", clear_on_submit=True):
                            new_title = st.text_input("Title", value=title)
                            new_description = st.text_area("Description", value=description)
                            new_due_date = st.date_input("Due Date", value=due_date_obj)
                            new_category = st.text_input("Category", value=category)
                            new_priority = st.selectbox("Priority", ["Low", "Med", "High"], index=["Low", "Med", "High"].index(priority))
                            if st.form_submit_button("Save Changes"):
                                update_task(task_id, new_title, new_description, new_due_date, new_category, new_priority)
                                st.success("Task updated successfully.")
                                st.rerun()

                with col3:
                    if user_type == "Restricted":
                        if st.button("Delete", key=f"delete_{task_id}"):
                            st.warning("Upgrade your plan to delete tasks.")
                    else:
                        if st.button("Delete", key=f"delete_{task_id}"):
                            delete_task(task_id)
                            st.success("Task deleted successfully.")
                            st.rerun()

        else:
            st.info("No tasks available.")

    with tab2:
        st.subheader("Add a Task")
        title = st.text_input("Title")
        description = st.text_area("Description")
        due_date = st.date_input("Due Date", min_value=datetime.now().date())
        category = st.text_input("Category")
        priority = st.selectbox("Priority", ["Low", "Med", "High"])
        if st.button("Add Task"):
            add_task(user_id, title, description, due_date, category, priority)
            st.success("Task added successfully!")
            st.rerun()

    with tab3:
        st.subheader("Statistics")
        completed_tasks = get_tasks(user_id, filter_by="completed")
        uncompleted_tasks = get_tasks(user_id, filter_by="uncompleted")
        total_tasks = len(completed_tasks) + len(uncompleted_tasks)

        st.write(f"Total Tasks: {total_tasks}")
        st.write(f"Completed Tasks: {len(completed_tasks)}")
        st.write(f"Uncompleted Tasks: {len(uncompleted_tasks)}")

        if completed_tasks:
            st.write("Completed Tasks:")
            for task in completed_tasks:
                st.write(f"- {task[1]}")

if __name__ == "__main__":
    main()
