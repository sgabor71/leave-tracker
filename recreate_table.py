import sqlite3

# Step 1: Connect to the SQLite database
conn = sqlite3.connect('leave_tracker.db')
cursor = conn.cursor()

# Step 2: Drop the existing settings table (warning: this deletes data)
cursor.execute("DROP TABLE IF EXISTS settings")

# Step 3: Recreate the settings table with the 'remaining_balance' column
cursor.execute('''CREATE TABLE settings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    remaining_balance REAL DEFAULT 0)''')

conn.commit()
conn.close()

print("Settings table recreated with 'remaining_balance' column.")
