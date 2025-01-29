import os
import json
from collections import OrderedDict
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton,
                             QScrollArea, QFileDialog)
from PyQt5.QtCore import Qt

LAUNCH_DATA_FILE = "past_launches.json"

# Load past launch data
def load_past_launches():
    if os.path.exists(LAUNCH_DATA_FILE):
        with open(LAUNCH_DATA_FILE, "r") as f:
            return json.load(f)
    return {}

# Save past launch data
def save_past_launches(data):
    with open(LAUNCH_DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

class PastLaunchesScreen(QWidget):
    def __init__(self, switch_to_summary, switch_to_main_menu):
        super().__init__()
        self.layout = QVBoxLayout(self)

        self.switch_to_summary = switch_to_summary
        self.switch_to_main_menu = switch_to_main_menu

        # Load past launches
        self.past_launches = load_past_launches()

        # Scrollable area for past launches
        self.scroll_area = QScrollArea()
        self.scroll_widget = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_widget)

        self.populate_launches()

        self.scroll_widget.setLayout(self.scroll_layout)
        self.scroll_area.setWidget(self.scroll_widget)
        self.scroll_area.setWidgetResizable(True)
        self.layout.addWidget(self.scroll_area)

        # Add "Return to Main Menu" button
        back_button = QPushButton("Return to Main Menu", self)
        back_button.setStyleSheet("font-size: 18px; padding: 10px;")
        back_button.clicked.connect(switch_to_main_menu)
        self.layout.addWidget(back_button)

    def populate_launches(self):
        print("Populating launches...")
        print("Current launches:", self.past_launches)  # Debug

        # Clear current launches
        for i in reversed(range(self.scroll_layout.count())):
            item = self.scroll_layout.itemAt(i)
            widget = item.widget()
            if widget:  # Only call setParent if the item has a widget
                widget.setParent(None)

        # Add launches in reverse order for newest first
        for launch_id, launch in reversed(self.past_launches.items()):
            print(f"Adding launch: {launch_id}")  # Debug
            launch_layout = QHBoxLayout()

            # Editable name field
            name_field = QLineEdit(launch.get("name", launch_id))
            name_field.editingFinished.connect(lambda id=launch_id, field=name_field: self.rename_launch(id, field.text()))
            launch_layout.addWidget(name_field)

            # View button
            view_button = QPushButton("View")
            view_button.clicked.connect(lambda _, id=launch_id: self.switch_to_summary(id))
            launch_layout.addWidget(view_button)

            # Download button
            download_button = QPushButton("Download")
            download_button.clicked.connect(lambda _, id=launch_id: self.download_data(id))
            launch_layout.addWidget(download_button)

            self.scroll_layout.addLayout(launch_layout)


    def rename_launch(self, launch_id, new_name):
        self.past_launches[launch_id]["name"] = new_name
        save_past_launches(self.past_launches)

    def download_data(self, launch_id):
        filename, _ = QFileDialog.getSaveFileName(self, "Save Launch Data", f"{launch_id}.txt", "Text Files (*.txt)")
        if filename:
            with open(filename, "w") as file:
                file.write("\n".join(self.past_launches[launch_id]["data"]))

    def add_new_launch(self, launch_id, launch_data):
        # Store the new launch at the beginning of the dictionary
        self.past_launches[launch_id] = launch_data
        save_past_launches(self.past_launches)

        # Create and insert only the new launch UI at the top
        launch_layout = QHBoxLayout()

        # Editable name field
        name_field = QLineEdit(launch_data.get("name", launch_id))
        name_field.editingFinished.connect(lambda id=launch_id, field=name_field: self.rename_launch(id, field.text()))
        launch_layout.addWidget(name_field)

        # View button
        view_button = QPushButton("View")
        view_button.clicked.connect(lambda _, id=launch_id: self.switch_to_summary(id))
        launch_layout.addWidget(view_button)

        # Download button
        download_button = QPushButton("Download")
        download_button.clicked.connect(lambda _, id=launch_id: self.download_data(id))
        launch_layout.addWidget(download_button)

        # Insert new launch at the top of the UI
        self.scroll_layout.insertLayout(0, launch_layout)

