import sqlite3

# Step 1: Connect to your SQLite database
conn = sqlite3.connect('leave_tracker.db')  # Update the path if your DB is elsewhere
cursor = conn.cursor()

# Step 2: Try to add the 'remaining_balance' column
try:
    # This command will add the 'remaining_balance' column to the settings table
    cursor.execute("ALTER TABLE settings ADD COLUMN remaining_balance REAL DEFAULT 0")
    conn.commit()
    print("Column 'remaining_balance' added successfully.")
except sqlite3.OperationalError as e:
    # If the column already exists, it will show an error message
    print(f"Error: {e}")

# Step 3: Close the connection
conn.close()
