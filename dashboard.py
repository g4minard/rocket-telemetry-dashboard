import sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QLabel, QWidget, QHBoxLayout, QPushButton, QStackedWidget, QGridLayout
from PyQt5.QtCore import QTimer, Qt
from mock_serial import MockSerial
import pyqtgraph as pg
import serial
import threading
import time
import numpy as np
from scipy.interpolate import make_interp_spline

class MainMenu(QWidget):
    def __init__(self, switch_to_dashboard):
        super().__init__()
        self.layout = QVBoxLayout(self)

        # Title label
        title_label = QLabel("[Rocket Name] Telemetry", self)
        title_label.setStyleSheet("font-size: 32px; font-weight: bold; text-align: center;")
        title_label.setAlignment(Qt.AlignCenter)
        self.layout.addWidget(title_label)

        # Launch button
        launch_button = QPushButton("LAUNCH", self)
        launch_button.setStyleSheet(
            "font-size: 36px; font-weight: bold; background-color: red; color: white; border-radius: 100px; padding: 50px;"
        )
        launch_button.clicked.connect(switch_to_dashboard)

        # Center the button
        button_container = QHBoxLayout()
        button_container.addStretch()
        button_container.addWidget(launch_button)
        button_container.addStretch()

        self.layout.addLayout(button_container)
        self.layout.addStretch()

class FlightDataApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Flight Computer Data")
        self.setGeometry(100, 100, 800, 600)

        # Stacked widget to hold screens
        self.stacked_widget = QStackedWidget()
        self.setCentralWidget(self.stacked_widget)

        # Main menu screen
        self.main_menu = MainMenu(self.switch_to_dashboard)
        self.stacked_widget.addWidget(self.main_menu)

        # Dashboard screen
        self.dashboard = Dashboard(self.switch_to_summary)
        self.stacked_widget.addWidget(self.dashboard)

        # Summary screen
        self.summary_screen = SummaryScreen()
        self.stacked_widget.addWidget(self.summary_screen)

        # Show the main menu by default
        self.stacked_widget.setCurrentWidget(self.main_menu)

    def switch_to_dashboard(self):
        self.stacked_widget.setCurrentWidget(self.dashboard)
        self.dashboard.start_serial_thread()

    def switch_to_summary(self):
        self.summary_screen.update_graphs(self.dashboard.data_history, self.dashboard.time_history)
        self.stacked_widget.setCurrentWidget(self.summary_screen)

class Dashboard(QWidget):
    def __init__(self, switch_to_summary):
        super().__init__()
        self.layout = QVBoxLayout(self)

        # Create a horizontal layout for graphs
        self.graph_layout = QHBoxLayout()
        self.layout.addLayout(self.graph_layout)

        # Create line graphs for each data field
        self.graphs = {}
        self.data_history = {"Velocity": [], "Altitude": [], "Temperature": [], "Pressure": []}  # Store all data points
        self.time_history = []  # Store all timestamps for x-axis

        self.colors = {
            "Velocity": "#7BAFD4",
            "Altitude": "#990000",
            "Temperature": "#0C2340",
            "Pressure": "#AE9142"
        }

        for field in self.data_history:
            plot_widget = pg.PlotWidget(title=f"{field}: ---", labels={'left': field, 'bottom': "Time (s)"})
            plot_widget.setLabel("left", field)
            plot_widget.setLabel("bottom", "Time", "s")
            self.graph_layout.addWidget(plot_widget)
            self.graphs[field] = (plot_widget.plot(pen=pg.mkPen(self.colors[field], width=2)), plot_widget)

        # Add summary button
        summary_button = QPushButton("VIEW SUMMARY", self)
        summary_button.setStyleSheet("font-size: 18px; font-weight: bold; background-color: orange; color: white; padding: 10px;")
        summary_button.clicked.connect(switch_to_summary)
        self.layout.addWidget(summary_button)

        # Start a timer to update the GUI and graphs
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_gui)
        self.timer.start(150)  # Update every 150ms

        # Initialize serial data
        self.data = {}
        self.serial_thread = None
        self.start_time = time.time()

    def start_serial_thread(self):
        if self.serial_thread is None or not self.serial_thread.is_alive():
            self.serial_thread = threading.Thread(target=self.read_serial_data, daemon=True)
            self.serial_thread.start()

    def read_serial_data(self):
        ser = MockSerial()

        while True:
            line = ser.readline().decode('utf-8').strip()
            if line:
                self.process_serial_data(line)

    def process_serial_data(self, data):
        try:
            fields = data.split(',')
            for field in fields:
                key, value = field.split(':')
                self.data[key] = float(value)  # Store values as floats for graphing
        except ValueError:
            print(f"Invalid data format: {data}")

    def interpolate_data(self, x, y, num_points=50):
        if len(x) < 2 or len(y) < 2:
            return x, y  # Not enough data to interpolate
        unique_x, unique_indices = np.unique(x, return_index=True)
        unique_y = np.array(y)[unique_indices]
        if len(unique_x) < 2:
            return x, y  # Still not enough data to interpolate
        try:
            spline = make_interp_spline(unique_x, unique_y, k=1)  # Use linear spline (k=1) for robustness
            smooth_x = np.linspace(unique_x[0], unique_x[-1], num_points)
            smooth_y = spline(smooth_x)
            return smooth_x, smooth_y
        except Exception as e:
            print(f"Interpolation error: {e}")
            return x, y

    def update_gui(self):
        # Update graph data
        current_time = time.time() - self.start_time  # Calculate elapsed time

        for key, (plot, plot_widget) in self.graphs.items():
            if key in self.data:
                # Append data only if the key exists
                self.data_history[key].append(self.data[key])
                self.time_history.append(current_time)

                # Ensure x and y are the same size
                if len(self.data_history[key]) > len(self.time_history):
                    self.data_history[key] = self.data_history[key][-len(self.time_history):]
                elif len(self.time_history) > len(self.data_history[key]):
                    self.time_history = self.time_history[-len(self.data_history[key]):]

                # Keep a rolling window of 100 points for dashboard graphs
                rolling_data = self.data_history[key][-100:]
                rolling_time = self.time_history[-100:]

                # Apply interpolation for smoothness
                smooth_time, smooth_data = self.interpolate_data(rolling_time, rolling_data, num_points=50)

                # Update the plot
                plot.setData(smooth_time, smooth_data)

                # Update the title with the current value
                plot_widget.setTitle(f"{key}: {self.data[key]:.2f}", color=self.colors[key])

class SummaryScreen(QWidget):
    def __init__(self):
        super().__init__()
        self.layout = QGridLayout(self)

        # Create graph placeholders
        self.graphs = {}
        fields = ["Velocity", "Altitude", "Temperature", "Pressure"]
        for i, field in enumerate(fields):
            plot_widget = pg.PlotWidget(title=field)
            plot_widget.setLabel("left", field)
            plot_widget.setLabel("bottom", "Time (s)")
            self.layout.addWidget(plot_widget, i // 2, i % 2)  # Arrange in a 2x2 grid
            self.graphs[field] = plot_widget

    def update_graphs(self, data_history, time_history):
        for key, plot_widget in self.graphs.items():
            if key in data_history:
                x = np.array(time_history)
                y = np.array(data_history[key])

                # Remove duplicate x-values and corresponding y-values
                unique_x, unique_indices = np.unique(x, return_index=True)
                unique_y = y[unique_indices]

                # Interpolate for smoothness
                if len(unique_x) > 2:
                    try:
                        spline = make_interp_spline(unique_x, unique_y, k=1)
                        smooth_x = np.linspace(unique_x[0], unique_x[-1], 500)
                        smooth_y = spline(smooth_x)
                    except Exception as e:
                        print(f"Interpolation error in summary: {e}")
                        smooth_x, smooth_y = unique_x, unique_y
                else:
                    smooth_x, smooth_y = unique_x, unique_y

                plot_widget.plot(smooth_x, smooth_y, pen=pg.mkPen(width=2), clear=True)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = FlightDataApp()
    window.show()
    sys.exit(app.exec_())
