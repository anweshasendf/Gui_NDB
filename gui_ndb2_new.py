import sys
import pandas as pd
import sqlite3
from nptdms import TdmsFile
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QLineEdit, QTableWidget, QTableWidgetItem, QFileDialog, QTabWidget, QMessageBox
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap
from PyQt5.QtGui import QImage, QBrush, QPalette
from PyQt5.QtCore import QObject, pyqtSignal, QRunnable, QThreadPool
from PyQt5.QtCore import QTimer
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtCore import QUrl
from logger import logger
from pdf2image import convert_from_path
import fitz
import numpy as np
import subprocess
import json
import traceback
import logging
from reportlab.platypus import PageBreak
import io
from PyQt5.QtWidgets import QApplication
import os
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QLineEdit, QTableWidget, QTableWidgetItem, QFileDialog, QTabWidget, QMessageBox
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QPixmap, QImage, QBrush, QPalette
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image, PageBreak, KeepTogether
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader
from reportlab.lib.enums import TA_LEFT
from PyQt5.QtWidgets import QScrollArea, QGroupBox
from reportlab.lib.units import inch
from reportlab.platypus import KeepTogether
from pdf2image import convert_from_path
import io
from PyQt5.QtGui import QImage
import tempfile
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Image
from reportlab.lib.pagesizes import letter
import matplotlib
matplotlib.use('Agg')  # Use the 'Agg' backend which is thread-safe
import matplotlib.pyplot as plt
from matplotlib.backends.backend_agg import FigureCanvasAgg
from io import BytesIO


# Database connection
def check_credentials(user_id, password):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id=? AND password=?", (user_id, password))
    result = cursor.fetchone()
    conn.close()
    return result


class PDFGeneratorWorker(QObject):
    finished = pyqtSignal()
    error = pyqtSignal(str)
    progress = pyqtSignal(str)


    def __init__(self, output_path, tab_widget, logo_path, data):
        super().__init__()
        self.output_path = output_path
        self.tab_widget = tab_widget
        self.logo_path = logo_path
        self.data = data
        self.temp_dir = tempfile.mkdtemp() 

    def run(self):
        try:
            logging.debug("Starting PDF generation")
            self.progress.emit("Starting PDF generation")
            pdf_gen = PDFGenerator(self.output_path, self.data, self.temp_dir)
            pdf_gen.add_cover_page(self.logo_path)

            for i in range(self.tab_widget.count()):
                tab = self.tab_widget.widget(i)
                tab_name = self.tab_widget.tabText(i)
                
                if tab_name.lower() == "Generate New PDF":
                    continue
                
                pdf_gen.add_page()
                pdf_gen.add_title(tab_name)

                table_widgets = tab.findChildren(QTableWidget)
                for table_widget in table_widgets:
                    pdf_gen.add_table(table_widget)
                    
                if tab_name in self.data['plots']:
                    plot_data = self.data['plots'][tab_name]['combined']
                    try:
                        temp_plot_path = self.save_plot_as_image(plot_data, f"temp_plot_{i}.png")
                        if os.path.exists(temp_plot_path):
                            pdf_gen.add_plot(temp_plot_path, plot_data['title'])
                        else:
                            logging.warning(f"Temp plot file not found: {temp_plot_path}")
                            pdf_gen.elements.append(Paragraph(f"Plot image not available for {tab_name}", pdf_gen.styles['Normal']))
                        
                        # Add NDB value and other new data
                        if tab_name in self.data['tables']:
                            table_data = self.data['tables'][tab_name]
                            ndb_value = table_data['data'][0][9]  # "Zero of NDB lies at" is at index 9
                            pdf_gen.elements.append(Paragraph(f"Zero of NDB lies at: {ndb_value}", pdf_gen.styles['Normal']))
                            
                            # Add new data
                            a1 = float(table_data['data'][0][2])
                            b1 = float(table_data['data'][0][4])
                            ndb_value_calc = abs(a1) - abs(b1)
                            a_band = table_data['data'][0][7]
                            b_band = table_data['data'][0][8]
                            delta_a1 = table_data['data'][0][10]
                            delta_a2 = table_data['data'][0][11]
                            delta_b1 = table_data['data'][0][12]
                            delta_b2 = table_data['data'][0][13]
                            
                            pdf_gen.elements.append(Paragraph(f"NDB Value: {ndb_value_calc:.2f}", pdf_gen.styles['Normal']))
                            pdf_gen.elements.append(Paragraph(f"A band: {a_band:.2f}", pdf_gen.styles['Normal']))
                            pdf_gen.elements.append(Paragraph(f"B band: {b_band:.2f}", pdf_gen.styles['Normal']))
                            pdf_gen.elements.append(Paragraph(f"Delta @ A1: {delta_a1:.2f}", pdf_gen.styles['Normal']))
                            pdf_gen.elements.append(Paragraph(f"Delta @ A2: {delta_a2:.2f}", pdf_gen.styles['Normal']))
                            pdf_gen.elements.append(Paragraph(f"Delta @ B1: {delta_b1:.2f}", pdf_gen.styles['Normal']))
                            pdf_gen.elements.append(Paragraph(f"Delta @ B2: {delta_b2:.2f}", pdf_gen.styles['Normal']))
                            pdf_gen.elements.append(Spacer(1, 12))
                    except Exception as plot_error:
                        logging.error(f"Error processing plot for tab {tab_name}: {str(plot_error)}")
                        pdf_gen.elements.append(Paragraph(f"Error processing plot: {str(plot_error)}", pdf_gen.styles['Normal']))
                        
            logging.debug("Saving PDF")
            self.progress.emit("Saving PDF")
            pdf_gen.save()
            logging.debug("PDF generation completed")
            self.progress.emit("PDF generation completed")
            self.finished.emit()
        except Exception as e:
            logging.error(f"Error in PDF generation: {str(e)}")
            logging.error(traceback.format_exc())
            self.error.emit(str(e))
        finally:
            # Clean up temporary directory
            if hasattr(self, 'temp_dir') and os.path.exists(self.temp_dir):
                for file in os.listdir(self.temp_dir):
                    try:
                        os.remove(os.path.join(self.temp_dir, file))
                    except Exception as e:
                        logging.error(f"Error removing temp file {file}: {str(e)}")
                try:
                    os.rmdir(self.temp_dir)
                except Exception as e:
                    logging.error(f"Error removing temp directory: {str(e)}")

    def save_plot_as_image(self, plot_data, filename):
        try:
            fig, ax = plt.figure(figsize=(12, 8)), plt.axes()  # Create figure and axes objects

            # Extract data from plot_data
            x_data = plot_data.get('x', [])
            y_data = plot_data.get('y', [])
            title = plot_data.get('title', '')
            x_label = plot_data.get('x_label', '')
            y_label = plot_data.get('y_label', '')

            # Plot the data
            ax.plot(x_data, y_data, 'b-')  # Blue line

            # Set title and labels
            ax.set_title(title)
            ax.set_xlabel(x_label)
            ax.set_ylabel(y_label)

            # Add grid
            ax.grid(True)

            # Adjust layout
            fig.tight_layout()

            # Save the figure to a BytesIO object
            buf = BytesIO()
            canvas = FigureCanvasAgg(fig)
            canvas.draw()
            plt.savefig(buf, format='png', dpi=300, bbox_inches='tight')
            plt.close(fig)

            # Save the BytesIO content to a file
            buf.seek(0)
            path = os.path.join(self.temp_dir, filename)
            with open(path, 'wb') as f:
                f.write(buf.getvalue())

            return path
        except Exception as e:
            logging.error(f"Error saving plot as image: {str(e)}")
            raise


class PDFGenerator:
    def __init__(self, filename, data, output_path):
        self.filename = filename
        self.elements = []
        self.data = data
        self.output_path = output_path
        self.doc = SimpleDocTemplate(filename, pagesize=letter, 
                                     leftMargin=36, rightMargin=36, 
                                     topMargin=36, bottomMargin=36)
        self.temp_dir = tempfile.mkdtemp()  # Create a temporary directory
        self.temp_files = []
        self.styles = getSampleStyleSheet()

    def add_page(self):
        self.elements.append(PageBreak())

    def add_cover_page(self, logo_path):
        self.elements.append(Paragraph("Neutral Deadband Test Results", self.styles['Title']))
        self.elements.append(Spacer(1, 12))
        if logo_path:
            img = Image(logo_path, width=2*inch, height=2*inch)
            self.elements.append(img)
            self.elements.append(Spacer(1, 12))

    def add_title(self, title):
        self.elements.append(Paragraph(title, self.styles['Heading1']))
        self.elements.append(Spacer(1, 12))

    def add_table(self, table_widget):
        data = []
        headers = []
        for col in range(table_widget.columnCount()):
            headers.append(Paragraph(table_widget.horizontalHeaderItem(col).text(), self.styles['Normal']))
        data.append(headers)
        
        for row in range(table_widget.rowCount()):
            row_data = []
            for col in range(table_widget.columnCount()):
                item = table_widget.item(row, col)
                cell_text = item.text() if item else ""
                row_data.append(Paragraph(cell_text, self.styles['Normal']))
            data.append(row_data)

        # Calculate column widths
        col_widths = [self.doc.width / len(headers)] * len(headers)
        
        table = Table(data, colWidths=col_widths, repeatRows=1)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 8),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 7),
            ('TOPPADDING', (0, 1), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 3),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        self.elements.append(table)
        self.elements.append(Spacer(1, 12))
        
    def save_plot_as_image(self, fig, filename):
        path = os.path.join(self.temp_dir, filename)
        fig.savefig(path)
        self.temp_files.append(path)  # Add to list of temp files
        return path

    #def add_plot(self, plot_path, title, plot_data, fig):
        #self.elements.append(Paragraph(title, self.styles['Heading2']))
        #img_path = self.save_plot_as_image(fig, f"temp_plot_{len(self.temp_files)}.png")
        #img = Image(plot_path, width=7*inch, height=5*inch)
        #img_1 = Image(img_path, width=7*inch, height=5*inch)
        #self.elements.append(img)
        #self.elements.append(img_1)
        #self.elements.append(Spacer(1, 12))
        
    def add_plot(self, plot_path, title):
        self.elements.append(Paragraph(title, self.styles['Heading2']))
        try:
            img = Image(plot_path, width=7*inch, height=5*inch)
            self.elements.append(img)
        except Exception as e:
            logging.error(f"Error adding plot image: {str(e)}")
            self.elements.append(Paragraph(f"Error adding plot image: {str(e)}", self.styles['Normal']))
        self.elements.append(Spacer(1, 12))

    def save(self):
        try:
            self.doc.build(self.elements)
        except Exception as e:
            logging.error(f"Error building PDF: {str(e)}")
            raise





class LoginWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.showFullScreen()
        logger.info("App launched")
        self.setWindowTitle("Login")
        #self.setGeometry(100, 100, 950, 650)
        
        # Add image to the top-right corner
          #  desired size of the label

        

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
            self.option_window = OptionWindow()
            self.option_window.show()
        else:
            logger.info("Login failed")
            QMessageBox.critical(self, "Error", "Invalid credentials")

    def set_background_image(self, image_path):
        oImage = QImage(image_path)
        sImage = oImage.scaled(self.size(), Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
        palette = QPalette()
        palette.setBrush(QPalette.Window, QBrush(sImage))
        self.setPalette(palette)

    def resizeEvent(self, event):
        self.set_background_image(r"C:\Users\U436445\OneDrive - Danfoss\Documents\GitHub\GUI\Danfoss_BG.png")
        super().resizeEvent(event)
    
class OptionWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.showFullScreen()
        self.setWindowTitle("Select Option")
        #self.setGeometry(100, 100, 950, 650)
        

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)

        self.button_efficiency = QPushButton("Efficiency")
        self.button_efficiency.clicked.connect(self.open_efficiency_options)
        self.layout.addWidget(self.button_efficiency)

        self.button_hydrostatic = QPushButton("Hydrostatic")
        self.button_hydrostatic.clicked.connect(self.open_hydrostatic_options)
        self.layout.addWidget(self.button_hydrostatic)
        
        self.button_neural_deadband = QPushButton("Neural Deadband")
        self.button_neural_deadband.clicked.connect(self.open_upload_window)
        self.layout.addWidget(self.button_neural_deadband)

    def set_background_image(self, image_path):
        oImage = QImage(image_path)
        sImage = oImage.scaled(self.size(), Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
        palette = QPalette()
        palette.setBrush(QPalette.Window, QBrush(sImage))
        self.setPalette(palette)

    def resizeEvent(self, event):
        self.set_background_image(r"C:\Users\U436445\OneDrive - Danfoss\Documents\GitHub\GUI\Danfoss_BG.png")
        super().resizeEvent(event)
        
    def open_efficiency_options(self):
        self.close()
        self.efficiency_window = EfficiencyWindow()
        self.efficiency_window.show()

    def open_hydrostatic_options(self):
        self.close()
        self.hydrostatic_window = HydrostaticWindow()
        self.hydrostatic_window.show()
        
    def open_upload_window(self):
        self.close()
        self.upload_window = UploadWindow()
        self.upload_window.show()

class EfficiencyWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.showFullScreen()
        self.setWindowTitle("Efficiency Options")
        #self.setGeometry(100, 100, 950, 650)
        logger.info("Efficiency options window opened")
        
        

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)
        
        options = ["Efficiency", "LS Hystersis", "LS Linearity", "LS RR", "LS Speed Sweep", "PC Hyst", "PC Speed Sweep", "PC RR"]
        for option in options:
            button = QPushButton(option)
            button.clicked.connect(self.open_upload_window)
            self.layout.addWidget(button)

    def set_background_image(self, image_path):
        oImage = QImage(image_path)
        sImage = oImage.scaled(self.size(), Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
        palette = QPalette()
        palette.setBrush(QPalette.Window, QBrush(sImage))
        self.setPalette(palette)

    def resizeEvent(self, event):
        self.set_background_image(r"C:\Users\U436445\OneDrive - Danfoss\Documents\GitHub\GUI\Danfoss_BG.png")
        super().resizeEvent(event)
    
    def open_upload_window(self):
        self.close()
        self.upload_window = UploadWindow()
        self.upload_window.show()
        
    

class HydrostaticWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.showFullScreen()
        self.setWindowTitle("Hydrostatic Options")
        #self.setGeometry(100, 100, 950, 650)
        logger.info("Hydrostatic options window opened")
        
        

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)

        options = ["Null", "Full", "X"]
        for option in options:
            button = QPushButton(option)
            button.clicked.connect(self.open_upload_window)
            self.layout.addWidget(button)
            
    def set_background_image(self, image_path):
        oImage = QImage(image_path)
        sImage = oImage.scaled(self.size(), Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
        palette = QPalette()
        palette.setBrush(QPalette.Window, QBrush(sImage))
        self.setPalette(palette)

    def resizeEvent(self, event):
        self.set_background_image(r"C:\Users\U436445\OneDrive - Danfoss\Documents\GitHub\GUI\Danfoss_BG.png")
        super().resizeEvent(event)
        
    def open_upload_window(self):
        self.close()
        self.upload_window = UploadWindow()
        self.upload_window.show()

class UploadWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.showFullScreen()
        self.setWindowTitle("Upload TDMS File")
        #self.setGeometry(100, 100, 950, 650)
        logger.info("Upload window opened")
        
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)

        self.button_upload = QPushButton("Upload TDMS Folder")
        self.button_upload.clicked.connect(self.read_tdms_folder)
        self.layout.addWidget(self.button_upload)

    def read_tdms_folder(self):
        folder_path = QFileDialog.getExistingDirectory(self, "Open TDMS Folder", "")
        if folder_path:
            logger.info(f"Folder uploaded: {folder_path}")
            result = subprocess.run(["python", "ndb_test_new.py", folder_path], capture_output=True, text=True)
            
            logger.info(f"Script stdout: {result.stdout}")
            logger.info(f"Script stderr: {result.stderr}")

            if result.returncode == 0:
                try:
                    output = json.loads(result.stdout)
                    if isinstance(output, dict) and "error" in output:
                        raise ValueError(output["error"])
                    elif isinstance(output, dict) and "warning" in output:
                        logger.warning(output["warning"])
                        QMessageBox.warning(self, "Warning", output["warning"])
                    else:
                        for file_name in os.listdir(folder_path):
                            if file_name.startswith("Neural_Deadband_Results_") and file_name.endswith(".csv"):
                                file_path = os.path.join(folder_path, file_name)
                                df = pd.read_csv(file_path)
                                output['tables'][file_name] = {
                                    'data': df.values.tolist(),
                                    'columns': df.columns.tolist(),
                                    'index': df.index.tolist()
                                }
                        
                        self.close()
                        self.display_window = DisplayWindow(output, output)
                        self.display_window.show()
                except json.JSONDecodeError:
                    logger.error(f"Failed to parse script output: {result.stdout}")
                    QMessageBox.critical(self, "Error", "Failed to parse script output")
                except ValueError as e:
                    logger.error(f"Script error: {str(e)}")
                    QMessageBox.critical(self, "Error", str(e))
            else:
                logger.error(f"Script error: {result.stderr}")
                QMessageBox.critical(self, "Error", f"Script execution failed: {result.stderr}")

    def set_background_image(self, image_path):
        oImage = QImage(image_path)
        sImage = oImage.scaled(self.size(), Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
        palette = QPalette()
        palette.setBrush(QPalette.Window, QBrush(sImage))
        self.setPalette(palette)

    def resizeEvent(self, event):
        self.set_background_image(r"C:\Users\U436445\OneDrive - Danfoss\Documents\GitHub\GUI\Danfoss_BG.png")
        super().resizeEvent(event)
        
class ScriptUploadWindow(QMainWindow):
    def __init__(self, data, tdms_folder_path):
        super().__init__()
        self.showFullScreen()
        self.setWindowTitle("Upload Python Script")
        #self.setGeometry(100, 100, 950, 650)
        self.data = data
        self.tdms_folder_path = tdms_folder_path
        logger.info("Script upload window opened")
        
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)

        self.button_upload_script = QPushButton("Upload Python Script")
        self.button_upload_script.clicked.connect(self.upload_script)
        self.layout.addWidget(self.button_upload_script)

    def upload_script(self):
        script_path, _ = QFileDialog.getOpenFileName(self, "Open Python Script", "", "Python files (*.py)")
        if script_path:
            logger.info(f"Script uploaded: {script_path}")
            result = subprocess.run(["python", script_path, self.tdms_folder_path], capture_output=True, text=True)
            
            # Log the script output for debugging
            logger.info(f"Script stdout: {result.stdout}")
            logger.info(f"Script stderr: {result.stderr}")

            if result.returncode == 0:
                try:
                    ndb_results = json.loads(result.stdout)
                    self.close()
                    # Pass ndb_results as both data and script_results
                    self.display_window = DisplayWindow(ndb_results, ndb_results)
                    self.display_window.show()
                except json.JSONDecodeError:
                    logger.error(f"Failed to parse script output: {result.stdout}")
                    QMessageBox.critical(self, "Error", "Failed to parse script output")
            else:
                logger.error(f"Script error: {result.stderr}")
                QMessageBox.critical(self, "Error", f"Script execution failed: {result.stderr}")

    def set_background_image(self, image_path):
        oImage = QImage(image_path)
        sImage = oImage.scaled(self.size(), Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
        palette = QPalette()
        palette.setBrush(QPalette.Window, QBrush(sImage))
        self.setPalette(palette)

    def resizeEvent(self, event):
        self.set_background_image(r"C:\Users\U436445\OneDrive - Danfoss\Documents\GitHub\GUI\Danfoss_BG.png")
        super().resizeEvent(event)
           
class DisplayWindow(QMainWindow):
    def __init__(self, data, raw_data):
        super().__init__()
        self.showFullScreen()
        self.setWindowTitle("TDMS Data")
        #self.setGeometry(100, 100, 1200, 900)
        self.data = data
        #self.script_results = script_results
        self.raw_data = raw_data
        self.logo_path = r"C:\Users\U436445\OneDrive - Danfoss\Documents\GitHub\GUI\Danfoss_BG.png"  # Define the logo_path attribute

        print("Data received:", self.data)  # Debug print
        print("Script results received:", self.raw_data)  # Debug print

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)

        self.tab_widget = QTabWidget()
        self.layout.addWidget(self.tab_widget)
        
        self.pdf_button = QPushButton("Generate New PDF")
        self.pdf_button.clicked.connect(self.on_generate_pdf)
        self.layout.addWidget(self.pdf_button)
        
        
        self.progress_label = QLabel("Progress: ")
        self.layout.addWidget(self.progress_label)
        
        QTimer.singleShot(0, self.create_tabs)

    def create_tabs(self):
        self.create_summary_tab()
        self.create_data_tab()
        #self.create_script_results_tabs()
        self.create_plot_tabs()
        self.create_help_tab()
        
    
    def create_summary_tab(self):
        summary_tab = QWidget()
        summary_layout = QVBoxLayout(summary_tab)

        # First table
        table1 = QTableWidget()
        table1.setColumnCount(2)
        table1.setHorizontalHeaderLabels(["Metric", "Value"])

        # Count processed files
        processed_files = len(self.data['tables'])
        table1.insertRow(table1.rowCount())
        table1.setItem(table1.rowCount() - 1, 0, QTableWidgetItem("CSV Files from TDMS"))
        table1.setItem(table1.rowCount() - 1, 1, QTableWidgetItem(str(processed_files)))

        # Count plots with NDB value
        plots_with_ndb = sum(1 for file_name in self.data['plots'] if file_name in self.data['tables'])
        total_plots = len(self.data['plots'])
        table1.insertRow(table1.rowCount())
        table1.setItem(table1.rowCount() - 1, 0, QTableWidgetItem("Plots with NDB Value"))
        table1.setItem(table1.rowCount() - 1, 1, QTableWidgetItem(f"{plots_with_ndb}/{total_plots}"))

        # Check if NDB test passed
        #ndb_values = [self.data['tables'][file_name]['data'][0][9] for file_name in self.data['tables'] if file_name in self.data['plots']]
        #ndb_test_passed = sum(1 for ndb in ndb_values if ndb < 0) >= len(ndb_values) * 0.5
        
        ndb_values = []
        for file_name, table_data in self.data['tables'].items():
            if file_name in self.data['plots']:
                a1 = float(table_data['data'][0][2])
                b1 = float(table_data['data'][0][4])
                ndb_value = abs(a1) - abs(b1)
                ndb_values.append(ndb_value)
        
        mean_ndb_value = sum(ndb_values) / len(ndb_values) if ndb_values else 0 #Made singular 
        ndb_test_passed = sum(1 for ndb in ndb_values if ndb >= mean_ndb_value) >= len(ndb_values) * 0.5
        table1.insertRow(table1.rowCount())
        table1.setItem(table1.rowCount() - 1, 0, QTableWidgetItem(f"NDB Test Result if 50% files are above Mean NDB ({mean_ndb_value:.2f})"))
        table1.setItem(table1.rowCount() - 1, 1, QTableWidgetItem("Passed" if ndb_test_passed else "Failed"))

        table1.resizeColumnsToContents()
        table1.setMinimumSize(600, 200)  # Increase size
        
        # Center the first table
        table1_container = QWidget()
        table1_container_layout = QHBoxLayout(table1_container)
        table1_container_layout.addStretch()
        table1_container_layout.addWidget(table1)
        table1_container_layout.addStretch()
        
        summary_layout.addWidget(table1_container)

        # Add some vertical space
        summary_layout.addSpacing(20)

        # Second table
        table2 = QTableWidget()
        table2.setColumnCount(9)
        table2.setHorizontalHeaderLabels(["Filename", "Zero of NDB", "NDB Value", "A band", "B band", "Delta @ A1", "Delta @ A2", "Delta @ B1", "Delta @ B2"])
        
        max_ndb_value = float('-inf')
        max_ndb_filename = ""
        
        for file_name, table_data in self.data['tables'].items():
            if file_name in self.data['plots']:
                row_position = table2.rowCount()
                table2.insertRow(row_position)
                
               
                table2.setItem(row_position, 0, QTableWidgetItem(file_name))
                
               
                zero_of_ndb = self.format_float(table_data['data'][0][9])
                a1 = float(table_data['data'][0][2])
                b1 = float(table_data['data'][0][4])
                ndb_value = self.format_float(a1 - b1)
                ndb_value = abs(a1) - abs(b1)
                a_band = self.format_float(table_data['data'][0][7])
                b_band = self.format_float(table_data['data'][0][8])
                delta_a1 = self.format_float(table_data['data'][0][10])
                delta_a2 = self.format_float(table_data['data'][0][11])
                delta_b1 = self.format_float(table_data['data'][0][12])
                delta_b2 = self.format_float(table_data['data'][0][13])
                
                # Set values in table
                table2.setItem(row_position, 1, QTableWidgetItem(zero_of_ndb))
                #table2.setItem(row_position, 2, QTableWidgetItem(ndb_value))
                table2.setItem(row_position, 2, QTableWidgetItem(self.format_float(ndb_value)))

                table2.setItem(row_position, 3, QTableWidgetItem(a_band))
                table2.setItem(row_position, 4, QTableWidgetItem(b_band))
                table2.setItem(row_position, 5, QTableWidgetItem(delta_a1))
                table2.setItem(row_position, 6, QTableWidgetItem(delta_a2))
                table2.setItem(row_position, 7, QTableWidgetItem(delta_b1))
                table2.setItem(row_position, 8, QTableWidgetItem(delta_b2))
                if ndb_value > max_ndb_value:
                    max_ndb_value = ndb_value
                    max_ndb_filename = file_name

        table2.resizeColumnsToContents()
        table2.setMinimumSize(800, 200)  # Increased width

  
        table2_container = QWidget()
        table2_container_layout = QHBoxLayout(table2_container)
        table2_container_layout.addStretch()
        table2_container_layout.addWidget(table2)
        table2_container_layout.addStretch()
        
        summary_layout.addWidget(table2_container)
        best_ndb_label = QLabel(f"{max_ndb_filename} has the best NDB value of {self.format_float(max_ndb_value)}")
        best_ndb_label.setAlignment(Qt.AlignCenter)
        summary_layout.addWidget(best_ndb_label)


        

        self.tab_widget.insertTab(0, summary_tab, "Summary")
    
    def pdf_to_images(self, pdf_path, pages=2):
        images = []
        
        # For Windows, specify the poppler_path 
        poppler_path = r"C:\Users\U436445\Downloads\Poppler\poppler-24.02.0\Library\bin"  
        
        pdf_pages = convert_from_path(pdf_path, 
                                    first_page=1, 
                                    last_page=pages,
                                    poppler_path=poppler_path if os.name == 'nt' else None)
        
        for page in pdf_pages:
            img_byte_arr = io.BytesIO()
            page.save(img_byte_arr, format='PNG')
            img_byte_arr = img_byte_arr.getvalue()
            images.append(img_byte_arr)
        
        return images

    def create_help_tab(self):
        help_tab = QWidget()
        help_layout = QVBoxLayout(help_tab)
        
        scroll_area = QScrollArea()
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        
        pdf_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "help_document.pdf")
        
        if os.path.exists(pdf_path):
            try:
                # Convert PDF pages to images
                images = self.pdf_to_images(pdf_path, pages=2)  # Get first 2 pages
                
                for i, image_data in enumerate(images):
                    group_box = QGroupBox(f"Page {i+1}")
                    group_layout = QVBoxLayout(group_box)
                    
                    qimage = QImage.fromData(image_data)
                    pixmap = QPixmap.fromImage(qimage)
                    
                    # Scale the pixmap to a good size (e.g., 800px wide)
                    pixmap = pixmap.scaledToWidth(800, Qt.SmoothTransformation)
                    
                    image_label = QLabel()
                    image_label.setPixmap(pixmap)
                    image_label.setAlignment(Qt.AlignCenter)
                    group_layout.addWidget(image_label)
                    
                    scroll_layout.addWidget(group_box)
            
            except Exception as e:
                error_label = QLabel(f"Error loading PDF: {str(e)}")
                scroll_layout.addWidget(error_label)
        else:
            error_label = QLabel("Help document not found.")
            scroll_layout.addWidget(error_label)
        
        scroll_content.setLayout(scroll_layout)
        scroll_area.setWidget(scroll_content)
        scroll_area.setWidgetResizable(True)
        help_layout.addWidget(scroll_area)
        
        self.tab_widget.addTab(help_tab, "Help")

    
    
    def create_data_tab(self):
        data_tab = QWidget()
        data_layout = QVBoxLayout(data_tab)
        
        for table_name, table_data in self.data['tables'].items():
            # Only process tables that start with "Merged Data"
            if not table_name.startswith("Merged Data"):
                continue
            
            group_box = QGroupBox(table_name)
            group_layout = QVBoxLayout(group_box)
            
            df = pd.DataFrame(table_data['data'], columns=table_data['columns'], index=table_data['index'])
            
            table = QTableWidget()
            table.setColumnCount(len(df.columns))
            table.setHorizontalHeaderLabels(df.columns)
            table.setRowCount(len(df))
            
            # Use setItem in bulk for better performance
            for i, row in enumerate(df.itertuples(index=False)):
                for j, value in enumerate(row):
                    formatted_value = self.format_float(value)
                    table.setItem(i, j, QTableWidgetItem(formatted_value))
            
            table.resizeColumnsToContents()
            table.setMinimumWidth(int(self.width() * 0.8))  # Set table width to 80% of window width
            table.setMinimumHeight(450)  
            
            group_layout.addWidget(table)
            data_layout.addWidget(group_box)
        
        scroll_area = QScrollArea()
        scroll_area.setWidget(data_tab)
        scroll_area.setWidgetResizable(True)
        self.tab_widget.addTab(scroll_area, "Data")
        
    def format_float(self, value):
        if isinstance(value, float):
            return f"{value:.2f}"
        elif isinstance(value, (int, np.integer)):
            return str(value)
        else:
            return str(value)
        
    def create_plot_tabs(self):
        for file_name, file_plots in self.data['plots'].items():
            tab = QWidget()
            tab_layout = QVBoxLayout(tab)

            #
            plot_data = file_plots['combined']

            # Add plot title
            title_label = QLabel(plot_data['title'])
            title_label.setStyleSheet("font-weight: bold; font-size: 16px;")
            tab_layout.addWidget(title_label)

            # Add plot image
            pixmap = QPixmap(plot_data['path'])
            image_label = QLabel()
            image_label.setPixmap(pixmap)
            image_label.setScaledContents(True)
            image_label.setFixedSize(1200, 900)  # Increased size for better visibility

            scroll_area = QScrollArea()
            scroll_area.setWidget(image_label)
            scroll_area.setWidgetResizable(True)
            tab_layout.addWidget(scroll_area)

            # Add NDB value
            if file_name in self.data['tables']:
                table_data = self.data['tables'][file_name]
                ndb_value = table_data['data'][0][9]  # "Zero of NDB lies at" is at index 9
                ndb_label = QLabel(f"Zero of NDB lies at: {ndb_value}")
                ndb_label.setStyleSheet("font-weight: bold; font-size: 14px;")
                tab_layout.addWidget(ndb_label)

            for subtitle in plot_data['subtitles']:
                subtitle_label = QLabel(subtitle)
                subtitle_label.setStyleSheet("font-style: italic; font-size: 12px;")
                tab_layout.addWidget(subtitle_label)

            self.tab_widget.addTab(tab, file_name)
            
    def create_script_results_tabs(self):
    # Create tabs for tables
        for table_name, table_data in self.data['tables'].items():
            tab = QWidget()
            tab_layout = QVBoxLayout(tab)

            df = pd.DataFrame(table_data['data'], columns=table_data['columns'], index=table_data['index'])
            table = QTableWidget()
            table.setColumnCount(len(df.columns))
            table.setHorizontalHeaderLabels(df.columns)
            table.setRowCount(len(df))
            for i in range(len(df)):
                for j, col in enumerate(df.columns):
                    table.setItem(i, j, QTableWidgetItem(str(df.iat[i, j])))
            tab_layout.addWidget(table)

            self.tab_widget.addTab(tab, table_name)

        # Create tabs for plots
        created_plots = set()  # Keep track of plots we've already created
        for file_name, file_plots in self.data['plots'].items():
            for plot_type, plot_data in file_plots.items():
                # Create a unique identifier for this plot
                plot_id = f"{file_name} - {plot_type}"
                
                # Skip if we've already created this plot
                if plot_id in created_plots:
                    continue
                
                created_plots.add(plot_id)  # Mark this plot as created

                tab = QWidget()
                tab_layout = QVBoxLayout(tab)

                label = QLabel(plot_data['title'])
                tab_layout.addWidget(label)

                pixmap = QPixmap(plot_data['path'])
                image_label = QLabel()
                image_label.setPixmap(pixmap)
                image_label.setScaledContents(True)
                image_label.setFixedSize(1200, 1000)  # Set a fixed size for the image

                scroll_area = QScrollArea()
                scroll_area.setWidget(image_label)
                scroll_area.setWidgetResizable(True)
                tab_layout.addWidget(scroll_area)

                self.tab_widget.addTab(tab, plot_id)
            
    

    def on_generate_pdf(self):
        output_path, _ = QFileDialog.getSaveFileName(self, "Save PDF", "", "PDF files (*.pdf)")
        if output_path:
            try:
                self.pdf_worker = PDFGeneratorWorker(output_path, self.tab_widget, self.logo_path, self.data)
                self.pdf_thread = QThread()
                self.pdf_worker.moveToThread(self.pdf_thread)
                
                self.pdf_thread.started.connect(self.pdf_worker.run)
                self.pdf_worker.finished.connect(self.pdf_thread.quit)
                self.pdf_worker.finished.connect(self.pdf_worker.deleteLater)
                self.pdf_thread.finished.connect(self.pdf_thread.deleteLater)
                
                self.pdf_worker.finished.connect(self.on_pdf_generation_finished)
                self.pdf_worker.error.connect(self.on_pdf_generation_error)
                self.pdf_worker.progress.connect(self.update_progress)
                
                self.pdf_thread.start()

                # Disable the button while generating PDF
                self.pdf_button.setEnabled(False)
                self.pdf_button.setText("Generating PDF...")
                
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to generate PDF: {str(e)}")
            finally:
                self.progress_label.setText("Progress: PDF Generation Complete")

    def on_pdf_generation_finished(self):
        QMessageBox.information(self, "Success", "PDF generated successfully!")
        self.pdf_button.setEnabled(True)
        self.pdf_button.setText("Generate PDF")

    def on_pdf_generation_error(self, error_msg):
        QMessageBox.critical(self, "Error", f"Failed to generate PDF: {error_msg}")
        self.pdf_button.setEnabled(True)
        self.pdf_button.setText("Generate PDF")

    def update_progress(self, progress_msg):
        self.progress_label.setText(f"Progress: {progress_msg}")

    def plot_column(self, column):
        self.ax.clear()
        if pd.api.types.is_numeric_dtype(self.df[column]):
            self.df.plot(y=column, ax=self.ax, kind='line')
            self.ax.set_xlabel('Index')
            self.ax.set_ylabel(column)
            self.ax.set_title(f'{column} (Numeric Data)')
        else:
            self.ax.text(0.5, 0.5, f"Cannot plot non-numeric data: {column}", 
                         horizontalalignment='center', verticalalignment='center')
            self.ax.set_title(f'{column} (Non-numeric Data)')
        self.ax.tick_params(axis='x', rotation=45)
        self.canvas.draw()

    def next_column(self):
        self.current_column = (self.current_column + 1) % len(self.df.columns)
        self.plot_column(self.df.columns[self.current_column])

    def prev_column(self):
        self.current_column = (self.current_column - 1) % len(self.df.columns)
        self.plot_column(self.df.columns[self.current_column])

    def next_column(self):
        self.current_column = (self.current_column + 1) % len(self.df.columns)
        self.plot_column(self.df.columns[self.current_column])

    def prev_column(self):
        self.current_column = (self.current_column - 1) % len(self.df.columns)
        self.plot_column(self.df.columns[self.current_column])

    def set_background_image(self, image_path):
        oImage = QImage(image_path)
        sImage = oImage.scaled(self.size(), Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
        palette = QPalette()
        palette.setBrush(QPalette.Window, QBrush(sImage))
        self.setPalette(palette)

    def resizeEvent(self, event):
        self.set_background_image(r"C:\Users\U436445\OneDrive - Danfoss\Documents\GitHub\GUI\Danfoss_BG.png")
        super().resizeEvent(event)
        
if __name__ == "__main__":
    logger.info("App launched")
    
    app = QApplication(sys.argv)
    
    stylesheet = """
    QWidget {
        font-family: 'Segoe UI', Arial, sans-serif;
        font-size: 18px;
        font-weight: bold;
    }
    QPushButton {
        font-size: 20px;
        padding: 8px 16px;
        background-color: #D22B2B;
        color: white;
        border: none;
        border-radius: 4px;
        font-weight: bold;
    }
    QPushButton:hover {
        background-color: #C04000;
    }
    QPushButton:pressed {
        background-color: #004275;
    }
    QLabel {
        font-size: 18px;
    }
    QLineEdit {
        font-size: 18px;
        padding: 6px;
        border: 1px solid #BDBDBD;
        border-radius: 4px;
    }
    QTableWidget {
        font-size: 16px;
        gridline-color: #E0E0E0;
    }
    QTableWidget::item {
        padding: 6px;
    }
    QHeaderView::section {
        background-color: #F5F5F5;
        font-weight: bold;
        padding: 8px;
        border: none;
        border-bottom: 1px solid #E0E0E0;
    }
    QMessageBox {
        font-size: 18px;
    }
    QTabWidget::pane {
        border: 1px solid #E0E0E0;
    }
    QTabBar::tab {
        background-color: #F5F5F5;
        padding: 10px 20px;
        border: 1px solid #E0E0E0;
        border-bottom: none;
        border-top-left-radius: 4px;
        border-top-right-radius: 4px;
    }
    QTabBar::tab:selected {
        background-color: white;
        border-bottom: 1px solid white;
    }
    """
    app.setStyleSheet(stylesheet)
    
    
    login_window = LoginWindow()
    login_window.show()
    logger.info("App closed")
    sys.exit(app.exec_())
