import tkinter as tk 
from tkinter import simpledialog, messagebox, filedialog
import pandas as pd 
import sqlite3
from nptdms import TdmsFile
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from tkinter import ttk
from logger import logger

# Database connection
def check_credentials(user_id, password):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id=? AND password=?", (user_id, password))
    result = cursor.fetchone()
    conn.close()
    return result

# Login window
def login():
    logger.info("App launched")
    def validate_login():
        user_id = entry_user_id.get()
        password = entry_password.get()
        logger.info(f"Login attempt: User ID - {user_id}")
        if check_credentials(user_id, password):
            logger.info("Login successful")
            login_window.destroy()
            upload_file()
        else:
            logger.info("Login failed")
            messagebox.showerror("Error", "Invalid credentials")

    login_window = tk.Tk()
    login_window.title("Login")

    tk.Label(login_window, text="User ID").grid(row=0, column=0)
    tk.Label(login_window, text="Password").grid(row=1, column=0)

    entry_user_id = tk.Entry(login_window)
    entry_password = tk.Entry(login_window, show="*")

    entry_user_id.grid(row=0, column=1)
    entry_password.grid(row=1, column=1)

    tk.Button(login_window, text="Login", command=validate_login).grid(row=2, column=1)

    login_window.mainloop()

# File upload window
def upload_file():
    def read_tdms_file():
        file_path = filedialog.askopenfilename(filetypes=[("TDMS files", "*.tdms")])
        if file_path:
            logger.info(f"File uploaded: {file_path}")
            tdms_file = TdmsFile.read(file_path)
            data = {group.name: group.as_dataframe() for group in tdms_file.groups()}
            display_data(upload_window, data)

    upload_window = tk.Tk()
    upload_window.title("Upload TDMS File")

    tk.Button(upload_window, text="Upload TDMS File", command=read_tdms_file).pack()

    upload_window.mainloop()

# Data display window
def display_data(parent_window, data):
   
    
    parent_window.destroy()
    logger.info("Displaying data")
    display_window = tk.Tk()
    display_window.title("TDMS Data")
    display_window.geometry("800x600")

    notebook = ttk.Notebook(display_window)
    notebook.pack(fill=tk.BOTH, expand=True)

    for group_name, df in data.items():
        frame = ttk.Frame(notebook)
        notebook.add(frame, text=group_name)

        # Create Treeview
        tree = ttk.Treeview(frame)
        tree["columns"] = list(df.columns)
        tree["show"] = "headings"

        for column in df.columns:
            tree.heading(column, text=column)
            tree.column(column, width=100)

        for index, row in df.iterrows():
            tree.insert("", tk.END, values=list(row))

        tree.pack(fill=tk.BOTH, expand=True)

        # Plotting
        fig, ax = plt.subplots(figsize=(8, 4))
        canvas = FigureCanvasTkAgg(fig, master=frame)
        canvas_widget = canvas.get_tk_widget()
        canvas_widget.pack()

        current_column = [0]  # Use a list to store mutable state

        def plot_column(column):
            ax.clear()
            print(f"Plotting column: {column}")  # Debug print
            if pd.api.types.is_numeric_dtype(df[column]):
                df.plot(y=column, ax=ax, kind='line')
                ax.set_xlabel('Index')
                ax.set_ylabel(column)
                ax.set_title(f'{column} (Numeric Data)')
            elif pd.api.types.is_datetime64_any_dtype(df[column]):
                df.plot(x=column, y=df.columns[1], ax=ax, kind='line')
                ax.set_xlabel(column)
                ax.set_ylabel(df.columns[1])
                ax.set_title(f'{column} vs {df.columns[1]} (Time-based Data)')
            else:
                df[column].value_counts().plot(kind='bar', ax=ax)
                ax.set_xlabel(column)
                ax.set_ylabel('Count')
                ax.set_title(f'{column} (Categorical Data)')
            ax.tick_params(axis='x', rotation=45)
            canvas.draw()

        def next_column():
            current_column[0] = (current_column[0] + 1) % len(df.columns)
            print(f"Next column index: {current_column[0]}")  # Debug print
            plot_column(df.columns[current_column[0]])

        def prev_column():
            current_column[0] = (current_column[0] - 1) % len(df.columns)
            print(f"Previous column index: {current_column[0]}")  # Debug print
            plot_column(df.columns[current_column[0]])

        button_frame = ttk.Frame(frame)
        button_frame.pack()

        ttk.Button(button_frame, text="Previous", command=prev_column).pack(side=tk.LEFT)
        ttk.Button(button_frame, text="Next", command=next_column).pack(side=tk.LEFT)

        plot_column(df.columns[0])

    def on_closing():
        logger.info("App closed")
        display_window.quit()
        display_window.destroy()

    display_window.protocol("WM_DELETE_WINDOW", on_closing)
    display_window.mainloop()
    print(df.columns)
    print(df.dtypes)
    
     

if __name__ == "__main__":
    login()