import streamlit as st
import sqlite3
from datetime import datetime, timedelta
import calendar as cal

# Database setup
conn = sqlite3.connect("tasks.db")
c = conn.cursor()

c.execute("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    user_type TEXT NOT NULL
)
""")
c.execute("""
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    due_date TEXT,
    category TEXT,
    priority TEXT NOT NULL,
    completed INTEGER DEFAULT 0,
    FOREIGN KEY(user_id) REFERENCES users(id)
)
""")
conn.commit()

# Helper Functions
def add_task(user_id, title, description, due_date, category, priority):
    c.execute("INSERT INTO tasks (user_id, title, description, due_date, category, priority) VALUES (?, ?, ?, ?, ?, ?)", 
              (user_id, title, description, due_date, category, priority))
    conn.commit()

def get_tasks(user_id, filter_by=None, category=None):
    query = "SELECT id, title, description, due_date, category, priority, completed FROM tasks WHERE user_id = ?"
    params = [user_id]
    if filter_by == "completed":
        query += " AND completed = 1"
    elif filter_by == "uncompleted":
        query += " AND completed = 0"
    if category:
        query += " AND category = ?"
        params.append(category)
    c.execute(query, params)
    return c.fetchall()

def update_task_status(task_id, status):
    c.execute("UPDATE tasks SET completed = ? WHERE id = ?", (status, task_id))
    conn.commit()

def update_task(task_id, title, description, due_date, category, priority):
    c.execute("UPDATE tasks SET title = ?, description = ?, due_date = ?, category = ?, priority = ? WHERE id = ?", 
              (title, description, due_date, category, priority, task_id))
    conn.commit()

def delete_task(task_id):
    c.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    conn.commit()

def get_task_count(user_id):
    c.execute("SELECT COUNT(*) FROM tasks WHERE user_id = ?", (user_id,))
    return c.fetchone()[0]

def get_categories(user_id):
    c.execute("SELECT DISTINCT category FROM tasks WHERE user_id = ?", (user_id,))
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
        c.execute("SELECT id, user_type FROM users WHERE username = ? AND password = ?", (username, password))
        user = c.fetchone()
        if user:
            st.session_state["logged_in"] = True
            st.session_state["user_id"] = user[0]
            st.session_state["user_type"] = user[1]
            st.success(f"Welcome, {username}!")
            st.rerun()
        else:
            st.error("Invalid credentials. Please try again.")

def signup_page():
    st.subheader("Sign Up")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    user_type = st.selectbox("User Type", ["Premium", "Regular", "Restricted"])
    if st.button("Sign Up"):
        try:
            c.execute("INSERT INTO users (username, password, user_type) VALUES (?, ?, ?)", 
                      (username, password, user_type))
            conn.commit()
            st.success("Account created successfully. Please log in.")
        except sqlite3.IntegrityError:
            st.error("Username already exists.")

def logout():
    st.session_state["logged_in"] = False
    st.session_state["user_id"] = None
    st.session_state["user_type"] = None
    st.success("Logged out successfully!")
    st.rerun()

def task_dashboard(user_id, user_type):
    st.sidebar.title("Dashboard")
    st.sidebar.button("Logout", on_click=logout)
    
    if user_type == "Regular" or "Restricted":
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
                due_date_obj = datetime.strptime(due_date, "%Y-%m-%d")
                days_left = (due_date_obj - datetime.now()).days

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

                col1, col2 = st.columns([8, 2])
                with col1:
                    if st.button("Edit", key=f"edit_{task_id}"):
                        with st.form(f"edit_form_{task_id}", clear_on_submit=True):
                            new_title = st.text_input("Title", value=title)
                            new_description = st.text_area("Description", value=description)
                            new_due_date = st.date_input("Due Date", value=due_date_obj)
                            new_category = st.text_input("Category", value=category)
                            new_priority = st.selectbox("Priority", ["Low", "Med", "High"], index=["Low", "Med", "High"].index(priority))
                            if st.form_submit_button("Save Changes"):
                                update_task(task_id, new_title, new_description, new_due_date.strftime("%Y-%m-%d"), new_category, new_priority)
                                st.success("Task updated successfully!")
                                st.rerun()

                with col2:
                    if st.button("✅", key=f"status_{task_id}"):
                        update_task_status(task_id, 0 if completed else 1)
                        st.rerun()
                    if user_type != "Restricted" and st.button("🗑️", key=f"delete_{task_id}"):
                        delete_task(task_id)
                        st.success("Task deleted successfully!")
                        st.rerun()

    with tab2:
        st.subheader("Add New Task")
        if user_type == "Regular" and get_task_count(user_id) >= 10:
            st.error("Task limit reached. Upgrade to Premium to add unlimited tasks.")
        else:
            with st.form("add_task_form", clear_on_submit=True):
                title = st.text_input("Task Title")
                description = st.text_area("Task Description")
                due_date = st.date_input("Due Date")
                category = st.text_input("Category")
                priority = st.selectbox("Priority", ["Low", "Med", "High"])
                if st.form_submit_button("Add Task"):
                    if title.strip():
                        add_task(user_id, title, description, due_date.strftime("%Y-%m-%d"), category, priority)
                        st.success("Task added successfully!")
                        st.rerun()
                    else:
                        st.error("Title cannot be empty!")

    with tab3:
        st.subheader("Statistics")
        c.execute("SELECT COUNT(*) FROM tasks WHERE user_id = ? AND completed = 1", (user_id,))
        completed_tasks = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM tasks WHERE user_id = ? AND completed = 0", (user_id,))
        uncompleted_tasks = c.fetchone()[0]

        st.write(f"**Completed Tasks:** {completed_tasks}")
        st.write(f"**Uncompleted Tasks:** {uncompleted_tasks}")

if __name__ == "__main__":
    main()
