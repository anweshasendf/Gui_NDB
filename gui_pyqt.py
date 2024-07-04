import sys
import pandas as pd
import sqlite3
from nptdms import TdmsFile
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QLineEdit, QTableWidget, QTableWidgetItem, QFileDialog, QTabWidget, QMessageBox
from PyQt5.QtCore import Qt
from logger import logger

# Database connection
def check_credentials(user_id, password):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id=? AND password=?", (user_id, password))
    result = cursor.fetchone()
    conn.close()
    return result


class LoginWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        logger.info("App launched")
        self.setWindowTitle("Login")
        self.setGeometry(100, 100, 300, 150)

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)

        self.label_user_id = QLabel("User ID")
        self.layout.addWidget(self.label_user_id)
        self.entry_user_id = QLineEdit()
        self.layout.addWidget(self.entry_user_id)

        self.label_password = QLabel("Password")
        self.layout.addWidget(self.label_password)
        self.entry_password = QLineEdit()
        self.entry_password.setEchoMode(QLineEdit.Password)
        self.layout.addWidget(self.entry_password)
        logger.info(f"Login attempt: User ID - {self.entry_user_id.text()}")

        self.button_login = QPushButton("Login")
        self.button_login.clicked.connect(self.validate_login)
        self.layout.addWidget(self.button_login)

    def validate_login(self):
        user_id = self.entry_user_id.text()
        password = self.entry_password.text()
        logger.info(f"Login attempt: User ID - {user_id}")
        if check_credentials(user_id, password):
            logger.info("Login successful")
            self.close()
            self.upload_window = UploadWindow()
            self.upload_window.show()
        else:
            logger.info("Login failed")
            QMessageBox.critical(self, "Error", "Invalid credentials")
import subprocess
class UploadWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        
        self.setWindowTitle("Upload TDMS File")
        self.setGeometry(100, 100, 300, 150)
        logger.info("Upload window opened")

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)

        self.button_upload = QPushButton("Upload TDMS File")
        self.button_upload.clicked.connect(self.read_tdms_file)
        self.layout.addWidget(self.button_upload)
        
    def preprocess_and_display(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Open TDMS File", "", "TDMS files (*.tdms)")
        if file_path:
            logger.info(f"File uploaded: {file_path}")
            # Call the preprocessing script
            subprocess.run(["python", "preprocess_script.py", file_path])
            tdms_file = TdmsFile.read(file_path)
            data = {group.name: group.as_dataframe() for group in tdms_file.groups()}
            self.close()
            self.display_window = DisplayWindow(data)
            self.display_window.show()

    def read_tdms_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Open TDMS File", "", "TDMS files (*.tdms)")
        if file_path:
            logger.info(f"File uploaded: {file_path}")
            tdms_file = TdmsFile.read(file_path)
            data = {group.name: group.as_dataframe() for group in tdms_file.groups()}
            self.close()
            self.display_window = DisplayWindow(data)
            self.display_window.show()

class DisplayWindow(QMainWindow):
    def __init__(self, data):
        super().__init__()
        self.setWindowTitle("TDMS Data")
        self.setGeometry(100, 100, 800, 600)
        self.data = data
        logger.info("Displaying data")

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)

        self.tab_widget = QTabWidget()
        self.layout.addWidget(self.tab_widget)

        for group_name, df in self.data.items():
            tab = QWidget()
            tab_layout = QVBoxLayout(tab)

            # Create Table
            table = QTableWidget()
            table.setColumnCount(len(df.columns))
            table.setHorizontalHeaderLabels(df.columns)
            table.setRowCount(len(df))
            for i in range(len(df)):
                for j in range(len(df.columns)):
                    table.setItem(i, j, QTableWidgetItem(str(df.iat[i, j])))
            tab_layout.addWidget(table)

            # Plotting
            self.fig, self.ax = plt.subplots(figsize=(8, 4))
            self.canvas = FigureCanvas(self.fig)
            tab_layout.addWidget(self.canvas)

            self.current_column = 0
            self.df = df

            button_layout = QHBoxLayout()
            self.button_prev = QPushButton("Previous")
            self.button_prev.clicked.connect(self.prev_column)
            button_layout.addWidget(self.button_prev)

            self.button_next = QPushButton("Next")
            self.button_next.clicked.connect(self.next_column)
            button_layout.addWidget(self.button_next)

            tab_layout.addLayout(button_layout)

            self.tab_widget.addTab(tab, group_name)

            self.plot_column(self.df.columns[self.current_column])

    def plot_column(self, column):
        self.ax.clear()
        if pd.api.types.is_numeric_dtype(self.df[column]):
            self.df.plot(y=column, ax=self.ax, kind='line')
            self.ax.set_xlabel('Index')
            self.ax.set_ylabel(column)
            self.ax.set_title(f'{column} (Numeric Data)')
        elif pd.api.types.is_datetime64_any_dtype(self.df[column]):
            self.df.plot(x=column, y=self.df.columns[1], ax=self.ax, kind='line')
            self.ax.set_xlabel(column)
            self.ax.set_ylabel(self.df.columns[1])
            self.ax.set_title(f'{column} vs {self.df.columns[1]} (Time-based Data)')
        else:
            self.df[column].value_counts().plot(kind='bar', ax=self.ax)
            self.ax.set_xlabel(column)
            self.ax.set_ylabel('Count')
            self.ax.set_title(f'{column} (Categorical Data)')
        self.ax.tick_params(axis='x', rotation=45)
        self.canvas.draw()

    def next_column(self):
        self.current_column = (self.current_column + 1) % len(self.df.columns)
        self.plot_column(self.df.columns[self.current_column])

    def prev_column(self):
        self.current_column = (self.current_column - 1) % len(self.df.columns)
        self.plot_column(self.df.columns[self.current_column])
    

if __name__ == "__main__":
    logger.info("App launched")
    app = QApplication(sys.argv)
    login_window = LoginWindow()
    login_window.show()
    logger.info("App closed")
    sys.exit(app.exec_())
    
    