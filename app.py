from flask import Flask, render_template, request, redirect, url_for
import sqlite3
from datetime import datetime, timedelta

app = Flask(__name__)

# Database setup
def init_db():
    conn = sqlite3.connect('leave_tracker.db')
    cursor = conn.cursor()

    # Drop existing tables if they exist
    cursor.execute("DROP TABLE IF EXISTS leave_balance")
    cursor.execute("DROP TABLE IF EXISTS leave_requests")

    # Create leave_balance table with correct columns
    cursor.execute('''CREATE TABLE leave_balance (
        id INTEGER PRIMARY KEY,
        initial_balance REAL DEFAULT 32,
        manual_adjustment REAL DEFAULT 0)''')

    cursor.execute('''CREATE TABLE leave_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        start_date TEXT,
        end_date TEXT,
        hours_requested REAL,
        days_taken INTEGER,
        date_requested TEXT)''')

    # Insert initial balance record
    cursor.execute("INSERT INTO leave_balance (id, initial_balance, manual_adjustment) VALUES (1, 32, 0)")

    conn.commit()
    conn.close()

# Uncomment the line below to initialize the database (only run once)
# init_db()

# Default weekday hours (modifiable)
weekday_hours = {
    0: 7.5,  # Monday
    2: 10,   # Wednesday
    3: 11.5, # Thursday
    4: 8.5   # Friday
}

# Function to calculate remaining balance
def get_remaining_balance():
    conn = sqlite3.connect('leave_tracker.db')
    cursor = conn.cursor()

    # Get initial balance and manual adjustments
    cursor.execute("SELECT initial_balance, manual_adjustment FROM leave_balance WHERE id = 1")
    balance_row = cursor.fetchone()

    # Default to 32 if no record exists
    if balance_row is None:
        initial_balance = 32
        manual_adjustment = 0
    else:
        initial_balance, manual_adjustment = balance_row

    # Calculate total hours taken
    cursor.execute("SELECT SUM(hours_requested) FROM leave_requests")
    total_hours_taken = cursor.fetchone()[0] or 0

    conn.close()

    # Calculate and return remaining balance
    total_balance = initial_balance + manual_adjustment - total_hours_taken
    return round(total_balance, 2)  # Round to 2 decimal places for precision

# Function to calculate leave hours and days
def calculate_leave_hours(start_date_obj, end_date_obj):
    total_hours = 0
    valid_days_count = 0
    current_date = start_date_obj
    while current_date <= end_date_obj:
        if current_date.weekday() in weekday_hours:
            total_hours += weekday_hours[current_date.weekday()]
            valid_days_count += 1
        current_date += timedelta(days=1)
    return total_hours, valid_days_count

# Function to fetch leave requests and format dates
def get_leave_requests():
    conn = sqlite3.connect('leave_tracker.db')
    cursor = conn.cursor()
    cursor.execute("SELECT id, start_date, end_date, hours_requested, days_taken, date_requested FROM leave_requests ORDER BY start_date ASC")
    leave_requests = cursor.fetchall()
    conn.close()
    # Format dates to DD-MM-YYYY
    formatted_requests = []
    for request in leave_requests:
        formatted_request = (
            request[0], # id
            datetime.strptime(request[1], "%Y-%m-%d").strftime("%d-%m-%Y"), # start_date
            datetime.strptime(request[2], "%Y-%m-%d").strftime("%d-%m-%Y"), # end_date
            request[3], # hours_requested
            request[4], # days_taken
            datetime.strptime(request[5], "%Y-%m-%d %H:%M:%S").strftime("%d-%m-%Y %H:%M:%S") # date_requested
        )
        formatted_requests.append(formatted_request)
    return formatted_requests

# Home route
@app.route('/', methods=['GET', 'POST'])
def home():
    global weekday_hours
    error = None
    warning = None
    start_date = None
    end_date = None
    hours_requested = None

    if request.method == 'POST':
        # Manually update remaining balance
        if 'update_balance' in request.form:
            try:
                new_balance = float(request.form.get('new_balance', ''))

                # Validate the balance
                if new_balance < 0:
                    error = "Balance cannot be negative. Please enter a valid value."
                else:
                    # Open database connection
                    conn = sqlite3.connect('leave_tracker.db')
                    cursor = conn.cursor()

                    # Get initial balance
                    cursor.execute("SELECT initial_balance FROM leave_balance WHERE id = 1")
                    initial_balance = cursor.fetchone()[0]

                    # Calculate total hours taken
                    cursor.execute("SELECT SUM(hours_requested) FROM leave_requests")
                    total_hours_taken = cursor.fetchone()[0] or 0

                    # Calculate manual adjustment
                    manual_adjustment = new_balance - (initial_balance - total_hours_taken)

                    # Update manual adjustment in the database
                    cursor.execute("UPDATE leave_balance SET manual_adjustment = ? WHERE id = 1", (manual_adjustment,))
                    conn.commit()
                    conn.close()

                return redirect(url_for('home'))

            except ValueError:
                error = "Invalid input for remaining balance. Please enter a valid number."
            return redirect(url_for('home'))

        # Update weekday hours if custom hours are provided
        if 'update_hours' in request.form:
            try:
                # Extract new custom hours from form inputs
                for day, default_hours in weekday_hours.items():
                    weekday_hours[day] = float(request.form.get(f'day_{day}', default_hours))
            except ValueError:
                error = "Invalid input for custom hours. Please enter valid numbers for all weekdays."
            return redirect(url_for('home'))

        # Leave Request Submission
        # Check if start_date and end_date exist in the form
        if 'start_date' not in request.form or 'end_date' not in request.form:
            return render_template('index.html', 
                leave_requests=get_leave_requests(), 
                remaining_balance=get_remaining_balance(), 
                error="Start date and end date are required. Please fill in all fields.",
                weekday_hours=weekday_hours)
        
        start_date = request.form['start_date']
        end_date = request.form['end_date']
        hours_requested = request.form.get('hours_requested', '').strip()
        start_date_obj = datetime.strptime(start_date, "%Y-%m-%d")
        end_date_obj = datetime.strptime(end_date, "%Y-%m-%d")

        # Check for invalid date ranges
        if end_date_obj < start_date_obj:
            error = "End date cannot be before start date. Please check your dates and try again."
            return render_template('index.html', error=error, leave_requests=get_leave_requests(), remaining_balance=get_remaining_balance())

        # Check for overlapping leave requests
        conn = sqlite3.connect('leave_tracker.db')
        cursor = conn.cursor()
        cursor.execute("SELECT start_date, end_date FROM leave_requests")
        existing_requests = cursor.fetchall()
        conn.close()

        overlap_detected = False
        for existing_start, existing_end in existing_requests:
            existing_start = datetime.strptime(existing_start, "%Y-%m-%d")
            existing_end = datetime.strptime(existing_end, "%Y-%m-%d")
            if start_date_obj <= existing_end and end_date_obj >= existing_start:
                overlap_detected = True
                warning = "The selected dates overlap with an existing leave request. Are you sure you want to proceed?"
                break

        # If overlap is detected, show warning
        if overlap_detected:
            return render_template('index.html', 
                warning=warning, 
                start_date=start_date, 
                end_date=end_date, 
                hours_requested=hours_requested,
                leave_requests=get_leave_requests(), 
                remaining_balance=get_remaining_balance(),
                weekday_hours=weekday_hours)

        # Calculate hours and days
        if not hours_requested:
            hours_requested, days_taken = calculate_leave_hours(start_date_obj, end_date_obj)
        else:
            try:
                hours_requested = float(hours_requested)
                days_taken = (end_date_obj - start_date_obj).days + 1
            except ValueError:
                error = "Invalid input for hours requested. Please enter a valid number."
                return render_template('index.html', error=error, leave_requests=get_leave_requests(), remaining_balance=get_remaining_balance())

        remaining_balance = get_remaining_balance()
        if hours_requested > remaining_balance:
            error = "You do not have enough annual leave hours left for this request. Please check your remaining balance and try again."
            return render_template('index.html', 
                error=error, 
                leave_requests=get_leave_requests(), 
                remaining_balance=remaining_balance,
                weekday_hours=weekday_hours)

        # Insert the request into the database
        conn = sqlite3.connect('leave_tracker.db')
        cursor = conn.cursor()
        cursor.execute('''INSERT INTO leave_requests (start_date, end_date, hours_requested, days_taken, date_requested)
        VALUES (?, ?, ?, ?, ?)''', (start_date, end_date, hours_requested, days_taken, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        conn.close()
        return redirect(url_for('home'))

    return render_template('index.html', 
        leave_requests=get_leave_requests(), 
        remaining_balance=get_remaining_balance(), 
        error=error, 
        weekday_hours=weekday_hours)

# New route to handle proceeding with overlapping request
@app.route('/proceed_with_request', methods=['POST'])
def proceed_with_request():
    start_date = request.form['start_date']
    end_date = request.form['end_date']
    hours_requested = request.form.get('hours_requested', '')

    if not start_date or not end_date:
        return redirect(url_for('home'))

    start_date_obj = datetime.strptime(start_date, "%Y-%m-%d")
    end_date_obj = datetime.strptime(end_date, "%Y-%m-%d")

    # Calculate hours and days
    if not hours_requested:
        hours_requested, days_taken = calculate_leave_hours(start_date_obj, end_date_obj)
    else:
        hours_requested = float(hours_requested)
        days_taken = (end_date_obj - start_date_obj).days + 1

    remaining_balance = get_remaining_balance()
    if hours_requested > remaining_balance:
        error = "You do not have enough annual leave hours left for this request."
        return render_template('index.html', 
            error=error, 
            leave_requests=get_leave_requests(), 
            remaining_balance=remaining_balance,
            weekday_hours=weekday_hours)

    # Insert the request into the database
    conn = sqlite3.connect('leave_tracker.db')
    cursor = conn.cursor()
    cursor.execute('''INSERT INTO leave_requests (start_date, end_date, hours_requested, days_taken, date_requested)
    VALUES (?, ?, ?, ?, ?)''', (start_date, end_date, hours_requested, days_taken, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()
    return redirect(url_for('home'))

# Delete route
@app.route('/delete/<int:request_id>', methods=['POST'])
def delete_request(request_id):
    conn = sqlite3.connect('leave_tracker.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM leave_requests WHERE id = ?", (request_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('home'))

# Reset route
@app.route('/reset', methods=['POST'])
def reset_leave_summary():
    conn = sqlite3.connect('leave_tracker.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM leave_requests")
    conn.commit()
    conn.close()
    return redirect(url_for('home'))

if __name__ == '__main__':
    app.run(debug=True)