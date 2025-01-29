import sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QLabel, QWidget, QHBoxLayout, QPushButton, QStackedWidget, QGridLayout
from PyQt5.QtCore import QTimer, Qt
from mock_serial import MockSerial
from past_launches import PastLaunchesScreen, load_past_launches, save_past_launches
import pyqtgraph as pg
import threading
import time
from datetime import datetime
import numpy as np
from scipy.interpolate import make_interp_spline

class MainMenu(QWidget):
    def __init__(self, switch_to_dashboard, switch_to_past_launches):
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

        # View past launches button
        past_launches_button = QPushButton("View Past Launches", self)
        past_launches_button.setStyleSheet("font-size: 24px;")
        past_launches_button.clicked.connect(switch_to_past_launches)
        self.layout.addWidget(past_launches_button)

class FlightDataApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Flight Computer Data")
        self.setGeometry(100, 100, 800, 600)

        # Stacked widget to hold screens
        self.stacked_widget = QStackedWidget()
        self.setCentralWidget(self.stacked_widget)

        # Main menu screen
        self.main_menu = MainMenu(self.switch_to_dashboard, self.switch_to_past_launches)
        self.stacked_widget.addWidget(self.main_menu)

        # Past launches screen
        self.past_launches_screen = PastLaunchesScreen(self.switch_to_summary, self.switch_to_main_menu)
        self.stacked_widget.addWidget(self.past_launches_screen)

        # Dashboard screen (pass past_launches_screen reference)
        self.dashboard = Dashboard(self.switch_to_summary, self.past_launches_screen)
        self.stacked_widget.addWidget(self.dashboard)

        # Summary screen
        self.summary_screen = SummaryScreen(self.switch_to_past_launches)
        self.stacked_widget.addWidget(self.summary_screen)

        # Show the main menu by default
        self.stacked_widget.setCurrentWidget(self.main_menu)

    def switch_to_dashboard(self):
        self.dashboard.start_serial_thread()
        self.stacked_widget.setCurrentWidget(self.dashboard)

    def switch_to_summary(self, launch_id=None):
        if launch_id:
            self.summary_screen.update_graphs_by_id(launch_id)
        else:
            self.summary_screen.update_graphs(self.dashboard.data_history, self.dashboard.time_history)
        self.stacked_widget.setCurrentWidget(self.summary_screen)

    def switch_to_past_launches(self):
        self.stacked_widget.setCurrentWidget(self.past_launches_screen)

    def switch_to_main_menu(self):
        self.stacked_widget.setCurrentWidget(self.main_menu)

class Dashboard(QWidget):
    def __init__(self, switch_to_summary, past_launches_screen):
        super().__init__()
        self.layout = QVBoxLayout(self)
        self.switch_to_summary = switch_to_summary
        self.past_launches_screen = past_launches_screen  # Store reference to past_launches_screen

        # Create a horizontal layout for graphs
        self.graph_layout = QHBoxLayout()
        self.layout.addLayout(self.graph_layout)

        # Create line graphs for each data field
        self.graphs = {}
        self.data_history = {"Velocity": [], "Altitude": [], "Temperature": [], "Pressure": []}
        self.time_history = []

        self.colors = {
            "Velocity": "#7BAFD4",
            "Altitude": "#990000",
            "Temperature": "#0A843D",
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
        summary_button.clicked.connect(lambda: [self.save_current_launch(), switch_to_summary()])
        self.layout.addWidget(summary_button)

        # Initialize serial data
        self.data = {}
        self.serial_thread = None
        self.serial_running = threading.Event()
        self.start_time = time.time()

        # Start a timer to update the GUI and graphs
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_gui)
        self.timer.start(150)  # Update every 150ms

    def save_current_launch(self):
        if not self.time_history:
            print("No data to save.")
            return

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        past_launches = load_past_launches()

        past_launches[timestamp] = {
            "name": timestamp,
            "data": [
                f"Velocity:{v},Altitude:{a},Temperature:{t},Pressure:{p}"
                for v, a, t, p in zip(
                    self.data_history["Velocity"],
                    self.data_history["Altitude"],
                    self.data_history["Temperature"],
                    self.data_history["Pressure"]
                )
            ]
        }

        save_past_launches(past_launches)
        print(f"Launch data saved as {timestamp}")

        # Use the reference to update past_launches_screen
        self.past_launches_screen.add_new_launch(timestamp, past_launches[timestamp])

    def start_serial_thread(self):
        if self.serial_thread is None or not self.serial_thread.is_alive():
            self.serial_running.set()
            self.serial_thread = threading.Thread(target=self.read_serial_data, daemon=True)
            self.serial_thread.start()

    def read_serial_data(self):
        ser = MockSerial()

        while self.serial_running.is_set():
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
        current_time = time.time() - self.start_time  # Calculate elapsed time

        for key, (plot, plot_widget) in self.graphs.items():
            if key in self.data:
                self.data_history[key].append(self.data[key])
                self.time_history.append(current_time)

                if len(self.data_history[key]) > len(self.time_history):
                    self.data_history[key] = self.data_history[key][-len(self.time_history):]
                elif len(self.time_history) > len(self.data_history[key]):
                    self.time_history = self.time_history[-len(self.data_history[key]):]

                rolling_data = self.data_history[key][-100:]
                rolling_time = self.time_history[-100:]

                smooth_time, smooth_data = self.interpolate_data(rolling_time, rolling_data, num_points=50)
                plot.setData(smooth_time, smooth_data)
                plot_widget.setTitle(f"{key}: {self.data[key]:.2f}", color=self.colors[key])

class SummaryScreen(QWidget):
    def __init__(self, switch_to_past_launches):
        super().__init__()
        self.layout = QGridLayout(self)

        self.graphs = {}
        fields = ["Velocity", "Altitude", "Temperature", "Pressure"]
        for i, field in enumerate(fields):
            plot_widget = pg.PlotWidget(title=field)
            plot_widget.setLabel("left", field)
            plot_widget.setLabel("bottom", "Time (s)")
            self.layout.addWidget(plot_widget, i // 2, i % 2)
            self.graphs[field] = plot_widget

        back_button = QPushButton("Return to Past Launches", self)
        back_button.setStyleSheet("font-size: 18px; padding: 10px;")
        back_button.clicked.connect(switch_to_past_launches)
        self.layout.addWidget(back_button, 2, 0, 1, 2)

    def update_graphs(self, data_history, time_history):
        for key, plot_widget in self.graphs.items():
            if key in data_history:
                x = np.array(time_history)
                y = np.array(data_history[key])
                unique_x, unique_indices = np.unique(x, return_index=True)
                unique_y = y[unique_indices]

                if len(unique_x) > 2:
                    try:
                        spline = make_interp_spline(unique_x, unique_y, k=1)
                        smooth_x = np.linspace(unique_x[0], unique_x[-1], 500)
                        smooth_y = spline(smooth_x)
                    except Exception:
                        smooth_x, smooth_y = unique_x, unique_y
                else:
                    smooth_x, smooth_y = unique_x, unique_y

                plot_widget.plot(smooth_x, smooth_y, pen=pg.mkPen(width=2), clear=True)

    def update_graphs_by_id(self, launch_id):
        past_launches = load_past_launches()
        if launch_id not in past_launches:
            print(f"Launch ID {launch_id} not found.")
            return

        launch_data = past_launches[launch_id]["data"]
        time_history = list(range(len(launch_data)))
        field_data = {"Velocity": [], "Altitude": [], "Temperature": [], "Pressure": []}

        for line in launch_data:
            parts = dict(pair.split(":") for pair in line.split(","))
            for field in field_data:
                field_data[field].append(float(parts[field]))

        for field, plot_widget in self.graphs.items():
            plot_widget.plot(time_history, field_data[field], pen=pg.mkPen(width=2), clear=True)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = FlightDataApp()
    window.show()
    sys.exit(app.exec_())
