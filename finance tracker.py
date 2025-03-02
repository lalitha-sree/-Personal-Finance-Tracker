import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import sqlite3
from datetime import datetime
import calendar
import os

# Page configuration
st.set_page_config(
    page_title="Personal Finance Tracker",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Database setup
def init_db():
    conn = sqlite3.connect('finance_tracker.db')
    c = conn.cursor()
    
    # Create tables if they don't exist
    c.execute('''
    CREATE TABLE IF NOT EXISTS expenses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT,
        amount REAL,
        category TEXT,
        description TEXT
    )
    ''')
    
    c.execute('''
    CREATE TABLE IF NOT EXISTS budgets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category TEXT UNIQUE,
        amount REAL
    )
    ''')
    
    c.execute('''
    CREATE TABLE IF NOT EXISTS savings_goals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE,
        target_amount REAL,
        current_amount REAL,
        target_date TEXT
    )
    ''')
    
    conn.commit()
    return conn

# Initialize database
conn = init_db()

# Currency symbol
CURRENCY = "₹"

# Predefined expense categories
EXPENSE_CATEGORIES = [
    "Food & Dining", "Housing", "Transportation", "Utilities",
    "Healthcare", "Entertainment", "Shopping", "Education",
    "Personal Care", "Travel", "Investments", "Debt Payments", "Other"
]

# Navigation
def navigation():
    st.sidebar.title("Finance Tracker")
    pages = {
        "Dashboard": dashboard_page,
        "Expense Tracker": expense_tracker_page,
        "Budget Management": budget_management_page,
        "Savings Goals": savings_goals_page,
        "Data Analysis": data_analysis_page
    }
    
    selection = st.sidebar.radio("Navigate", list(pages.keys()))
    
    # Display selected page
    pages[selection]()
    
    st.sidebar.markdown("---")
    st.sidebar.info("Personal Finance Tracker v1.0")

# Dashboard page
def dashboard_page():
    st.title("Financial Dashboard")
    
    # Current month stats
    current_month = datetime.now().month
    current_year = datetime.now().year
    month_name = calendar.month_name[current_month]
    
    col1, col2, col3 = st.columns(3)
    
    # Expenses for current month
    query = f"SELECT SUM(amount) FROM expenses WHERE date LIKE '{current_year}-{current_month:02d}%'"
    total_expenses = conn.execute(query).fetchone()[0] or 0
    
    # Get budget for current month
    query = "SELECT SUM(amount) FROM budgets"
    total_budget = conn.execute(query).fetchone()[0] or 0
    
    # Get total savings
    query = "SELECT SUM(current_amount) FROM savings_goals"
    total_savings = conn.execute(query).fetchone()[0] or 0
    
    with col1:
        st.metric(
            label=f"Total Expenses ({month_name})",
            value=f"{CURRENCY}{total_expenses:.2f}",
            delta=f"{(1 - total_expenses/total_budget)*100:.1f}% of budget" if total_budget > 0 else None
        )
    
    with col2:
        st.metric(
            label="Total Budget",
            value=f"{CURRENCY}{total_budget:.2f}",
            delta=f"{CURRENCY}{total_budget - total_expenses:.2f} remaining" if total_budget > 0 else None
        )
    
    with col3:
        st.metric(
            label="Total Savings",
            value=f"{CURRENCY}{total_savings:.2f}"
        )
    
    # Charts section
    st.subheader("Monthly Overview")
    col1, col2 = st.columns(2)
    
    with col1:
        # Category breakdown for current month
        query = f"SELECT category, SUM(amount) as total FROM expenses WHERE date LIKE '{current_year}-{current_month:02d}%' GROUP BY category"
        df_expenses_by_category = pd.read_sql_query(query, conn)
        
        if not df_expenses_by_category.empty:
            fig = px.pie(
                df_expenses_by_category,
                values='total',
                names='category',
                title=f"Expense Breakdown - {month_name} {current_year}",
                hole=0.4
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No expenses recorded for this month.")
    
    with col2:
        # Budget vs Actual
        query = "SELECT b.category, b.amount as budget, COALESCE(e.amount, 0) as expense FROM budgets b LEFT JOIN (SELECT category, SUM(amount) as amount FROM expenses WHERE date LIKE ? GROUP BY category) e ON b.category = e.category"
        df_budget_vs_actual = pd.read_sql_query(query, conn, params=(f"{current_year}-{current_month:02d}%",))
        
        if not df_budget_vs_actual.empty:
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=df_budget_vs_actual['category'],
                y=df_budget_vs_actual['budget'],
                name='Budget',
                marker_color='blue'
            ))
            fig.add_trace(go.Bar(
                x=df_budget_vs_actual['category'],
                y=df_budget_vs_actual['expense'],
                name='Actual',
                marker_color='red'
            ))
            fig.update_layout(
                title=f"Budget vs Actual - {month_name} {current_year}",
                barmode='group',
                xaxis_title="Category",
                yaxis_title=f"Amount ({CURRENCY})"
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No budget data available.")
    
    # Recent transactions
    st.subheader("Recent Transactions")
    query = "SELECT date, amount, category, description FROM expenses ORDER BY date DESC LIMIT 5"
    df_recent = pd.read_sql_query(query, conn)
    
    if not df_recent.empty:
        # Format the amount column to show INR symbol
        df_recent['amount'] = df_recent['amount'].apply(lambda x: f"{CURRENCY}{x:.2f}")
        st.dataframe(df_recent, use_container_width=True)
    else:
        st.info("No transactions recorded yet.")

# Expense tracker page
def expense_tracker_page():
    st.title("Expense Tracker")
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.subheader("Add New Expense")
        with st.form("expense_form", clear_on_submit=True):
            date = st.date_input("Date", datetime.now())
            amount = st.number_input(f"Amount ({CURRENCY})", min_value=0.01, format="%.2f")
            category = st.selectbox("Category", EXPENSE_CATEGORIES)
            description = st.text_input("Description")
            
            submitted = st.form_submit_button("Add Expense")
            if submitted:
                c = conn.cursor()
                c.execute(
                    "INSERT INTO expenses (date, amount, category, description) VALUES (?, ?, ?, ?)",
                    (date.strftime("%Y-%m-%d"), amount, category, description)
                )
                conn.commit()
                st.success("Expense added successfully!")
    
    with col2:
        st.subheader("Recent Expenses")
        
        # Filter options
        col_a, col_b = st.columns(2)
        with col_a:
            month_filter = st.selectbox(
                "Filter by Month",
                ["All"] + list(calendar.month_name)[1:],
                index=datetime.now().month
            )
        
        with col_b:
            category_filter = st.selectbox(
                "Filter by Category",
                ["All"] + EXPENSE_CATEGORIES
            )
        
        # Create query with filters
        query = "SELECT id, date, amount, category, description FROM expenses"
        params = []
        where_clauses = []
        
        if month_filter != "All":
            month_num = list(calendar.month_name).index(month_filter)
            where_clauses.append("strftime('%m', date) = ?")
            params.append(f"{month_num:02d}")
        
        if category_filter != "All":
            where_clauses.append("category = ?")
            params.append(category_filter)
        
        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)
        
        query += " ORDER BY date DESC"
        
        df_expenses = pd.read_sql_query(query, conn, params=params)
        
        if not df_expenses.empty:
            # Display expenses with edit and delete options
            for _, row in df_expenses.iterrows():
                col_a, col_b, col_c = st.columns([3, 1, 1])
                
                with col_a:
                    st.write(f"**{row['date']}** - {row['category']}")
                    st.write(f"*{row['description']}*")
                
                with col_b:
                    st.write(f"**{CURRENCY}{row['amount']:.2f}**")
                
                with col_c:
                    if st.button("Delete", key=f"del_{row['id']}"):
                        c = conn.cursor()
                        c.execute("DELETE FROM expenses WHERE id = ?", (row['id'],))
                        conn.commit()
                        st.experimental_rerun()
                
                st.divider()
        else:
            st.info("No expenses found with the current filters.")

# Budget management page
def budget_management_page():
    st.title("Budget Management")
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.subheader("Set Budget")
        
        # Get existing budgets
        existing_budgets = {}
        cursor = conn.cursor()
        for row in cursor.execute("SELECT category, amount FROM budgets"):
            existing_budgets[row[0]] = row[1]
        
        with st.form("budget_form"):
            category = st.selectbox("Category", EXPENSE_CATEGORIES)
            current_budget = existing_budgets.get(category, 0.0)
            amount = st.number_input(
                f"Monthly Budget Amount ({CURRENCY})",
                min_value=0.0,
                value=current_budget,
                format="%.2f"
            )
            
            submitted = st.form_submit_button("Set Budget")
            if submitted:
                c = conn.cursor()
                c.execute(
                    "INSERT OR REPLACE INTO budgets (category, amount) VALUES (?, ?)",
                    (category, amount)
                )
                conn.commit()
                st.success(f"Budget for {category} set to {CURRENCY}{amount:.2f}")
    
    with col2:
        st.subheader("Current Budgets")
        
        # Current month and year
        current_month = datetime.now().month
        current_year = datetime.now().year
        
        # Get budget vs actual spending
        query = """
        SELECT 
            b.category, 
            b.amount as budget, 
            COALESCE(e.expense, 0) as spent,
            b.amount - COALESCE(e.expense, 0) as remaining,
            CASE WHEN e.expense IS NULL THEN 0 ELSE (e.expense / b.amount) * 100 END as percentage
        FROM 
            budgets b
        LEFT JOIN 
            (SELECT category, SUM(amount) as expense 
             FROM expenses 
             WHERE date LIKE ? 
             GROUP BY category) e 
        ON b.category = e.category
        ORDER BY percentage DESC
        """
        
        df_budget_status = pd.read_sql_query(
            query, conn, 
            params=(f"{current_year}-{current_month:02d}%",)
        )
        
        if not df_budget_status.empty:
            # Display budget progress bars
            for _, row in df_budget_status.iterrows():
                col_a, col_b = st.columns([3, 1])
                
                with col_a:
                    st.write(f"**{row['category']}**")
                    progress = min(row['percentage'] / 100, 1.0)
                    st.progress(progress)
                    
                with col_b:
                    st.write(f"{CURRENCY}{row['spent']:.2f} / {CURRENCY}{row['budget']:.2f}")
                    st.write(f"{CURRENCY}{row['remaining']:.2f} left")
                
                st.divider()
        else:
            st.info("No budgets have been set. Use the form to set your first budget.")

# Savings goals page
def savings_goals_page():
    st.title("Savings Goals")
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.subheader("Add Savings Goal")
        
        with st.form("savings_form", clear_on_submit=True):
            name = st.text_input("Goal Name")
            target_amount = st.number_input(f"Target Amount ({CURRENCY})", min_value=1.0, format="%.2f")
            current_amount = st.number_input(f"Current Amount ({CURRENCY})", min_value=0.0, format="%.2f")
            target_date = st.date_input("Target Date", datetime.now())
            
            submitted = st.form_submit_button("Add Goal")
            if submitted and name:
                c = conn.cursor()
                try:
                    c.execute(
                        "INSERT INTO savings_goals (name, target_amount, current_amount, target_date) VALUES (?, ?, ?, ?)",
                        (name, target_amount, current_amount, target_date.strftime("%Y-%m-%d"))
                    )
                    conn.commit()
                    st.success(f"Savings goal '{name}' added successfully!")
                except sqlite3.IntegrityError:
                    st.error(f"A goal with the name '{name}' already exists!")
    
    with col2:
        st.subheader("Update Savings")
        
        # Get all savings goals
        query = "SELECT id, name, target_amount, current_amount, target_date FROM savings_goals"
        df_goals = pd.read_sql_query(query, conn)
        
        if not df_goals.empty:
            # Display each goal with update option
            for _, row in df_goals.iterrows():
                col_a, col_b, col_c = st.columns([2, 2, 1])
                goal_id = row['id']
                
                with col_a:
                    st.write(f"**{row['name']}**")
                    progress = min(row['current_amount'] / row['target_amount'], 1.0)
                    st.progress(progress)
                    st.write(f"Target Date: {row['target_date']}")
                
                with col_b:
                    st.write(f"{CURRENCY}{row['current_amount']:.2f} / {CURRENCY}{row['target_amount']:.2f}")
                    percentage = (row['current_amount'] / row['target_amount']) * 100
                    st.write(f"{percentage:.1f}% complete")
                
                with col_c:
                    new_amount = st.number_input(
                        "Update Amount",
                        min_value=0.0,
                        value=row['current_amount'],
                        key=f"update_{goal_id}",
                        format="%.2f"
                    )
                    
                    if st.button("Update", key=f"btn_{goal_id}"):
                        c = conn.cursor()
                        c.execute(
                            "UPDATE savings_goals SET current_amount = ? WHERE id = ?",
                            (new_amount, goal_id)
                        )
                        conn.commit()
                        st.experimental_rerun()
                    
                    if st.button("Delete", key=f"del_{goal_id}"):
                        c = conn.cursor()
                        c.execute("DELETE FROM savings_goals WHERE id = ?", (goal_id,))
                        conn.commit()
                        st.experimental_rerun()
                
                st.divider()
        else:
            st.info("No savings goals have been created yet.")

# Data analysis page
def data_analysis_page():
    st.title("Financial Analysis")
    
    # Time period selection
    period = st.radio(
        "Select Time Period",
        ["Last 30 Days", "This Month", "Last 3 Months", "Last 6 Months", "This Year", "All Time"],
        horizontal=True
    )
    
    # Create date filter based on selection
    today = datetime.now()
    if period == "Last 30 Days":
        start_date = (today.replace(day=1) - pd.DateOffset(days=30)).strftime("%Y-%m-%d")
    elif period == "This Month":
        start_date = today.replace(day=1).strftime("%Y-%m-%d")
    elif period == "Last 3 Months":
        start_date = (today.replace(day=1) - pd.DateOffset(months=3)).strftime("%Y-%m-%d")
    elif period == "Last 6 Months":
        start_date = (today.replace(day=1) - pd.DateOffset(months=6)).strftime("%Y-%m-%d")
    elif period == "This Year":
        start_date = today.replace(month=1, day=1).strftime("%Y-%m-%d")
    else:  # All Time
        start_date = "2000-01-01"  # A date far in the past
    
    end_date = today.strftime("%Y-%m-%d")
    
    # Trends tab and Category tab
    tab1, tab2 = st.tabs(["Spending Trends", "Category Analysis"])
    
    with tab1:
        # Spending over time
        st.subheader("Spending Over Time")
        
        query = """
        SELECT 
            date, 
            SUM(amount) as total 
        FROM 
            expenses 
        WHERE 
            date BETWEEN ? AND ? 
        GROUP BY 
            date 
        ORDER BY 
            date
        """
        
        df_spending = pd.read_sql_query(query, conn, params=(start_date, end_date))
        
        if not df_spending.empty:
            df_spending['date'] = pd.to_datetime(df_spending['date'])
            df_spending.set_index('date', inplace=True)
            
            # Resample to fill in missing dates
            if period in ["This Year", "All Time"]:
                df_spending = df_spending.resample('M').sum()
            else:
                df_spending = df_spending.resample('D').sum().fillna(0)
            
            fig = px.line(
                df_spending, 
                x=df_spending.index, 
                y='total',
                title="Daily Spending",
                labels={'total': f'Amount ({CURRENCY})', 'date': 'Date'}
            )
            st.plotly_chart(fig, use_container_width=True)
            
            # Cumulative spending
            df_spending['cumulative'] = df_spending['total'].cumsum()
            fig = px.line(
                df_spending,
                x=df_spending.index,
                y='cumulative',
                title="Cumulative Spending",
                labels={'cumulative': f'Amount ({CURRENCY})', 'date': 'Date'}
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No spending data available for the selected period.")
    
    with tab2:
        # Category analysis
        st.subheader("Spending by Category")
        
        query = """
        SELECT 
            category, 
            SUM(amount) as total 
        FROM 
            expenses 
        WHERE 
            date BETWEEN ? AND ? 
        GROUP BY 
            category 
        ORDER BY 
            total DESC
        """
        
        df_categories = pd.read_sql_query(query, conn, params=(start_date, end_date))
        
        if not df_categories.empty:
            col1, col2 = st.columns(2)
            
            with col1:
                fig = px.pie(
                    df_categories,
                    values='total',
                    names='category',
                    title="Spending Distribution by Category",
                    hole=0.4
                )
                st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                fig = px.bar(
                    df_categories,
                    x='category',
                    y='total',
                    title="Total Spending by Category",
                    labels={'total': f'Amount ({CURRENCY})', 'category': 'Category'}
                )
                st.plotly_chart(fig, use_container_width=True)
            
            # Display category data in table
            st.subheader("Category Breakdown")
            
            # Add percentage column
            df_categories['percentage'] = (df_categories['total'] / df_categories['total'].sum() * 100).round(2)
            df_categories.rename(columns={'total': 'amount', 'percentage': 'percent_of_total'}, inplace=True)
            
            # Format columns
            df_display = df_categories.copy()
            df_display['amount'] = df_display['amount'].apply(lambda x: f"{CURRENCY}{x:.2f}")
            df_display['percent_of_total'] = df_display['percent_of_total'].apply(lambda x: f"{x}%")
            
            st.dataframe(df_display, use_container_width=True)
        else:
            st.info("No category data available for the selected period.")
        
        # Top expenses
        st.subheader("Top Expenses")
        
        query = """
        SELECT 
            date, 
            amount, 
            category, 
            description 
        FROM 
            expenses 
        WHERE 
            date BETWEEN ? AND ? 
        ORDER BY 
            amount DESC 
        LIMIT 10
        """
        
        df_top = pd.read_sql_query(query, conn, params=(start_date, end_date))
        
        if not df_top.empty:
            # Format amount column to show INR symbol
            df_formatted = df_top.copy()
            df_formatted['amount'] = df_formatted['amount'].apply(lambda x: f"{CURRENCY}{x:.2f}")
            st.dataframe(df_formatted, use_container_width=True)
        else:
            st.info("No expense data available for the selected period.")

# Main app
def main():
    # CSS styling
    st.markdown("""
        <style>
        .main .block-container {
            padding-top: 2rem;
        }
        </style>
    """, unsafe_allow_html=True)
    
    # App navigation
    navigation()

if __name__ == "__main__":
    main()