import sys
import os
import json
import csv
import requests
from datetime import datetime
from PyQt5.QtWidgets import (QApplication, QMainWindow, QTabWidget, QWidget, QVBoxLayout, QHBoxLayout, 
                            QLabel, QLineEdit, QPushButton, QProgressBar, QTextEdit, QFileDialog,
                            QMessageBox, QGroupBox, QCheckBox, QComboBox, QTableWidget, 
                            QTableWidgetItem, QHeaderView, QFrame)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QColor

class StatboticsClient:
    def __init__(self):
        # Statbotics API base URL
        self.base_url = "https://api.statbotics.io/v3"
        self.tba = None  # Will be set by the main app to avoid circular reference
        
    def get_event_data(self, event_key):
        """Get all relevant data for an event from Statbotics."""
        data = {}
        
        # Get basic event info
        data['event_info'] = self.get_api_data(f"/event/{event_key}")
        
        # Get teams at the event with their stats
        event_teams = self.get_api_data(f"/team_events?event={event_key}&limit=500")
        if event_teams:
            data['event_teams'] = event_teams
        
        # Get match predictions
        match_predictions = self.get_api_data(f"/matches?event={event_key}&limit=500")
        if match_predictions:
            data['match_predictions'] = match_predictions
            
        # Get team rankings
        team_rankings = self.get_api_data(f"/team_events?event={event_key}&metric=epa_rank&limit=500")
        if team_rankings:
            data['team_rankings'] = team_rankings
            
        return data

    def get_match_prediction(self, match_key):
        """Get prediction data for a specific match."""
        return self.get_api_data(f"/match/{match_key}")

    def get_api_data(self, endpoint):
        """Make a request to the Statbotics API."""
        url = self.base_url + endpoint
        print(url)
        try:
            response = requests.get(url)
            
            if response.status_code == 200:
                return response.json()
            else:
                print(f"Error: {response.status_code}")
                print(response.text)
                return None
        except Exception as e:
            print(f"API request error: {e}")
            return None

    def fetch_teams(self, eventkey):
        """Fetch teams from Statbotics API for an event."""
        if not self.tba:
            print("Error: TBA client not initialized")
            return []
            
        teams_data = self.tba.get_api_data(f"/event/{eventkey}/teams")
        teams = []
        if teams_data:
            for team in teams_data:
                if 'team_number' in team:
                    teams.append(team['team_number'])
        return teams

    def fetch_event_data(self, eventkey):
        """Fetch event data including teams and matches."""
        event_data = self.get_api_data(f"/event/{eventkey}")
        return event_data
    
    def fetch_team_epa(self, team_numbers):
        """Fetch EPA data for specific teams."""
        epa_data = []
        for team_number in team_numbers:
            try:
                data = self.get_api_data(f"/team/{team_number}")
                if data and "norm_epa" in data:
                    team_epa = {
                        "current": data.get("norm_epa", 0),
                        "recent": data.get("recent_epa", 0),
                        "mean": data.get("mean_epa", 0),
                        "max": data.get("max_epa", 0)
                    }
                    team_record = data.get("record", {})
                    epa_data.append((team_epa, team_record))
                else:
                    # Default values if data is missing
                    epa_data.append((
                        {"current": 0, "recent": 0, "mean": 0, "max": 0}, 
                        {"wins": 0, "losses": 0, "ties": 0, "winrate": 0}
                    ))
            except Exception as e:
                print(f"Error fetching EPA data for team {team_number}: {e}")
                # Default values on error
                epa_data.append((
                    {"current": 0, "recent": 0, "mean": 0, "max": 0}, 
                    {"wins": 0, "losses": 0, "ties": 0, "winrate": 0}
                ))
        return epa_data

    def fetch_match_data(self, matchkey):
        """Fetch match data from the Statbotics API."""
        match_data = self.get_api_data(f"/match/{matchkey}")
        return match_data


class BlueAllianceClient:
    def __init__(self):
        # TBA API base URL
        self.base_url = "https://www.thebluealliance.com/api/v3"
        # You need to get your own key from The Blue Alliance
        self.headers = {
            "X-TBA-Auth-Key": "2ujRBcLLwzp008e9TxIrLYKG6PCt2maIpmyiWtfWGl2bT6ddpqGLoLM79o56mx3W"  # Replace with your actual TBA API key
        }

    def fetch_teams(self, eventkey):
        """Fetch teams from the Statbotics API."""
        teams_data = self.get_api_data(f"/event/{eventkey}/teams")
        return teams_data

    def fetch_match_teams(self, matchkey):
        """Fetch teams for a specific match."""
        match_data = self.get_api_data(f"/match/{matchkey}/teams")
        for team in match_data:
            print(team['team_number'])
        return match_data

    def get_event_data(self, event_key):
        """Get all relevant data for an event."""
        data = {}
        
        # Get basic event info
        data['event_info'] = self.get_api_data(f"/event/{event_key}")
        
        # Get teams at the event
        data['teams'] = self.get_api_data(f"/event/{event_key}/teams")
        
        # Get matches with detailed breakdown
        matches = self.get_api_data(f"/event/{event_key}/matches")
        
        # For each match, get detailed scoring data if available
        if matches:
            for match in matches:
                # Ensure score_breakdown data is complete
                if 'score_breakdown' in match and match['score_breakdown']:
                    # Already has detailed scoring data
                    pass
                else:
                    # Get match details including score breakdown
                    match_detail = self.get_api_data(f"/match/{match['key']}")
                    if match_detail and 'score_breakdown' in match_detail:
                        match['score_breakdown'] = match_detail['score_breakdown']
                        
        data['matches'] = matches
        
        # Get rankings
        data['rankings'] = self.get_api_data(f"/event/{event_key}/rankings")
        
        # Get alliances
        data['alliances'] = self.get_api_data(f"/event/{event_key}/alliances")
        
        # Get match details with score breakdowns
        data['match_details'] = self.get_api_data(f"/event/{event_key}/matches")
        
        return data

    def get_api_data(self, endpoint):
        """Make a request to the TBA API."""
        url = self.base_url + endpoint
        print(url)
        response = requests.get(url, headers=self.headers)
        
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Error: {response.status_code}")
            print(response.text)
            return None

    def convert_to_csv(self, data, output_folder):
        """Convert the JSON data to CSV files."""
        if not os.path.exists(output_folder):
            os.makedirs(output_folder)
        
        csv_files = []
        
        # Process each data type
        for data_type, items in data.items():
            if not items:
                continue
                
            filename = os.path.join(output_folder, f"{data_type}.csv")
            csv_files.append(filename)
            
            if data_type == 'event_info':
                # Handle single object data
                self.single_object_to_csv(items, filename)
            elif data_type == 'rankings' and 'rankings' in items:
                # Special handling for rankings data structure
                self.rankings_to_csv(items, filename)
            elif data_type == 'matches':
                # Enhanced handling for match data with all scoring info
                self.matches_to_csv(items, filename)
            else:
                # Handle array of objects
                self.array_to_csv(items, filename)
                
        return csv_files

    def single_object_to_csv(self, data, filename):
        """Convert a single JSON object to CSV."""
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            # Write header
            writer.writerow(data.keys())
            # Write data
            writer.writerow(data.values())

    def array_to_csv(self, data, filename):
        """Convert an array of JSON objects to CSV."""
        if not data:
            return
            
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            # Get all possible fieldnames from all objects
            fieldnames = set()
            for item in data:
                fieldnames.update(self.flatten_keys(item))
            
            writer = csv.DictWriter(csvfile, fieldnames=sorted(fieldnames))
            writer.writeheader()
            for item in data:
                writer.writerow(self.flatten_dict(item))
    
    def flatten_dict(self, d, parent_key='', sep='_'):
        """Flatten nested dictionaries for CSV export."""
        items = []
        for k, v in d.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k
            if isinstance(v, dict):
                items.extend(self.flatten_dict(v, new_key, sep=sep).items())
            elif isinstance(v, list):
                if all(isinstance(item, dict) for item in v):
                    for i, item in enumerate(v):
                        items.extend(self.flatten_dict(item, f"{new_key}{sep}{i}", sep=sep).items())
                else:
                    items.append((new_key, json.dumps(v)))
            else:
                items.append((new_key, v))
        return dict(items)
        
    def flatten_keys(self, d, parent_key='', sep='_'):
        """Get all keys from a nested dictionary."""
        keys = []
        for k, v in d.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k
            if isinstance(v, dict):
                keys.extend(self.flatten_keys(v, new_key, sep=sep))
            elif isinstance(v, list) and all(isinstance(item, dict) for item in v):
                for i, item in enumerate(v):
                    keys.extend(self.flatten_keys(item, f"{new_key}{sep}{i}", sep=sep))
            else:
                keys.append(new_key)
        return keys

    def rankings_to_csv(self, data, filename):
        """Special handling for rankings data structure."""
        rankings = data.get('rankings', [])
        if not rankings:
            return
            
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            # Extract all possible fieldnames
            fieldnames = set()
            for ranking in rankings:
                fieldnames.update(ranking.keys())
                if 'extra_stats' in ranking:
                    fieldnames.remove('extra_stats')
                if 'sort_orders' in ranking:
                    fieldnames.remove('sort_orders')
                    
            # Add extra stats and sort orders with their names
            if rankings and 'extra_stats' in rankings[0]:
                for i, name in enumerate(data.get('extra_stats_info', [])):
                    fieldnames.add(f"extra_{name['name']}")
                    
            if rankings and 'sort_orders' in rankings[0]:
                for i, name in enumerate(data.get('sort_order_info', [])):
                    fieldnames.add(f"sort_{name['name']}")
            
            writer = csv.DictWriter(csvfile, fieldnames=sorted(fieldnames))
            writer.writeheader()
            
            for ranking in rankings:
                row = ranking.copy()
                
                # Handle extra_stats
                if 'extra_stats' in row:
                    extra_stats = row.pop('extra_stats')
                    for i, value in enumerate(extra_stats):
                        if i < len(data.get('extra_stats_info', [])):
                            name = data['extra_stats_info'][i]['name']
                            row[f"extra_{name}"] = value
                
                # Handle sort_orders
                if 'sort_orders' in row:
                    sort_orders = row.pop('sort_orders')
                    for i, value in enumerate(sort_orders):
                        if i < len(data.get('sort_order_info', [])):
                            name = data['sort_order_info'][i]['name']
                            row[f"sort_{name}"] = value
                
                writer.writerow(row)
                
    def matches_to_csv(self, matches, filename):
        """Enhanced handling for matches with all scoring information."""
        if not matches:
            return
            
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            # Get all possible fieldnames from all matches including deeply nested scoring data
            fieldnames = set()
            for match in matches:
                flat_match = self.flatten_dict(match)
                fieldnames.update(flat_match.keys())
            
            writer = csv.DictWriter(csvfile, fieldnames=sorted(fieldnames))
            writer.writeheader()
            
            for match in matches:
                flat_match = self.flatten_dict(match)
                writer.writerow(flat_match)


class FetchDataThread(QThread):
    """Thread for fetching data to prevent UI freezing."""
    progress_signal = pyqtSignal(int)
    status_signal = pyqtSignal(str)
    result_signal = pyqtSignal(dict)
    error_signal = pyqtSignal(str)

    def __init__(self, client, event_key, output_dir, update_existing):
        super().__init__()
        self.client = client
        self.event_key = event_key
        self.output_dir = output_dir
        self.update_existing = update_existing

    def run(self):
        # Removed try/except block
        self.status_signal.emit("Fetching data from The Blue Alliance...")
        self.progress_signal.emit(10)
        
        event_data = self.client.get_event_data(self.event_key)
        
        if not event_data['event_info']:
            self.error_signal.emit(f"Could not find event with key: {self.event_key}")
            return
                
        self.status_signal.emit("Converting data to CSV...")
        self.progress_signal.emit(50)
                
        # Determine output directory
        if self.update_existing:
            event_dir = os.path.join(self.output_dir, self.event_key)
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            event_dir = os.path.join(self.output_dir, f"{self.event_key}_{timestamp}")
                
        # Convert to CSV
        csv_files = self.client.convert_to_csv(event_data, event_dir)
                
        result = {
            'csv_files': csv_files,
            'event_dir': event_dir,
            'update_existing': self.update_existing
        }
                
        self.result_signal.emit(result)
        self.progress_signal.emit(100)


class FetchMatchDataThread(QThread):
    """Thread for fetching match data to prevent UI freezing."""
    progress_signal = pyqtSignal(int)
    status_signal = pyqtSignal(str)
    result_signal = pyqtSignal(dict)
    error_signal = pyqtSignal(str)

    def __init__(self, app, event_key, match_type, match_number, output_dir):
        super().__init__()
        self.app = app
        self.event_key = event_key
        self.match_type = match_type
        self.match_number = match_number
        self.output_dir = output_dir

    def run(self):
        # Removed try/except block
        match_key = f"{self.event_key}_{self.match_type}{self.match_number}"
            
        self.status_signal.emit("Fetching match data from The Blue Alliance...")
        self.progress_signal.emit(10)
            
        tba_match_data = self.app.tba_client.get_api_data(f"/match/{match_key}")
        if not tba_match_data:
            self.error_signal.emit(f"Could not find match with key: {match_key}")
            return
                
        self.progress_signal.emit(30)
            
        self.status_signal.emit("Fetching match predictions from Statbotics...")
        statbotics_match_data = self.app.statbotics_client.get_match_prediction(match_key)
            
        self.progress_signal.emit(50)
            
        teams = []
        if 'alliances' in tba_match_data:
            for alliance in ['red', 'blue']:
                if alliance in tba_match_data['alliances'] and 'team_keys' in tba_match_data['alliances'][alliance]:
                    teams.extend([team.replace('frc', '') for team in tba_match_data['alliances'][alliance]['team_keys']])
            
        if not teams:
            self.error_signal.emit("No teams found in match data")
            return
            
        self.progress_signal.emit(60)
            
        self.status_signal.emit(f"Fetching data for {len(teams)} teams...")
            
        teams_opr = self.app.tba_client.get_api_data(f"/event/{self.event_key}/oprs") or {}
        teams_int = [int(team) for team in teams if team.isdigit()]
        teams_epa = self.app.statbotics_client.fetch_team_epa(teams_int)
            
        team_data = {}
        for i, team in enumerate(teams):
            team_info = self.app.tba_client.get_api_data(f"/team/frc{team}")
                
            if team_info:
                epa_data = teams_epa[i] if i < len(teams_epa) else (
                    {"current": 0, "recent": 0, "mean": 0, "max": 0},
                    {"wins": 0, "losses": 0, "ties": 0, "winrate": 0}
                )
                    
                team_data[team] = {
                    "nickname": team_info.get('nickname', ''),
                    "name": team_info.get('name', ''),
                    "city": team_info.get('city', ''),
                    "state_prov": team_info.get('state_prov', ''),
                    "country": team_info.get('country', ''),
                    "opr": teams_opr.get("oprs", {}).get(f"frc{team}", 0),
                    "epa": epa_data
                }
            
        self.progress_signal.emit(80)
            
        combined_data = self.app.create_combined_match_data(tba_match_data, statbotics_match_data, team_data)
            
        output_filename = os.path.join(self.output_dir, f"{match_key}_combined.json")
        with open(output_filename, 'w') as f:
            json.dump(combined_data, f, indent=4)
            
        self.app.create_match_csv_files(combined_data, team_data, self.output_dir)
            
        result = {
            'output_dir': self.output_dir,
            'output_filename': output_filename,
            'combined_data': combined_data
        }
            
        self.result_signal.emit(result)
        self.progress_signal.emit(100)


class FetchTeamInsightsThread(QThread):
    """Thread for fetching team insights to prevent UI freezing."""
    progress_signal = pyqtSignal(int)
    status_signal = pyqtSignal(str)
    result_signal = pyqtSignal(dict)
    error_signal = pyqtSignal(str)

    def __init__(self, app, event_key, output_dir):
        super().__init__()
        self.app = app
        self.event_key = event_key
        self.output_dir = output_dir

    def run(self):
        # Removed try/except block
        self.status_signal.emit("Fetching teams for the event...")
        self.progress_signal.emit(5)
            
        teams_data = self.app.tba_client.get_api_data(f"/event/{self.event_key}/teams")
        if not teams_data:
            self.error_signal.emit(f"Could not find teams for event: {self.event_key}")
            return
            
        teams = [team['team_number'] for team in teams_data if 'team_number' in team]
        if not teams:
            self.error_signal.emit("No valid team numbers found")
            return
            
        self.status_signal.emit(f"Found {len(teams)} teams. Fetching OPR data...")
        self.progress_signal.emit(20)
            
        teams_opr = self.app.tba_client.get_api_data(f"/event/{self.event_key}/oprs") or {}
            
        self.status_signal.emit("Fetching EPA data from Statbotics...")
        self.progress_signal.emit(40)
            
        batch_size = 10
        all_csv_files = []
        for i in range(0, len(teams), batch_size):
            batch = teams[i:i + batch_size]
            self.status_signal.emit(f"Fetching EPA data for teams {i + 1}-{i + len(batch)} of {len(teams)}...")
            batch_epa = self.app.statbotics_client.fetch_team_epa(batch)
                
            batch_folder = os.path.join(self.output_dir, f"batch_{i // batch_size + 1}")
            os.makedirs(batch_folder, exist_ok=True)
                
            team_data = {}
            for j, team in enumerate(batch):
                team_info = teams_data[i + j] if i + j < len(teams_data) else {}
                epa_data, record = batch_epa[j] if j < len(batch_epa) else (
                    {"current": 0, "recent": 0, "mean": 0, "max": 0},
                    {"wins": 0, "losses": 0, "ties": 0, "winrate": 0}
                )
                team_data[team] = {
                    "nickname": team_info.get('nickname', ''),
                    "city": team_info.get('city', ''),
                    "state_prov": team_info.get('state_prov', ''),
                    "country": team_info.get('country', ''),
                    "opr": teams_opr.get("oprs", {}).get(f"frc{team}", 0),
                    "epa_current": epa_data.get("current", 0),
                    "epa_recent": epa_data.get("recent", 0),
                    "epa_mean": epa_data.get("mean", 0),
                    "epa_max": epa_data.get("max", 0),
                    "wins": record.get("wins", 0),
                    "losses": record.get("losses", 0),
                    "ties": record.get("ties", 0),
                    "win_rate": record.get("winrate", 0)
                }
                
            batch_csv_file = os.path.join(batch_folder, "Team_Insights.csv")
            with open(batch_csv_file, 'w', newline='', encoding='utf-8') as csvfile:
                fieldnames = [
                    'team', 'nickname', 'city', 'state', 'country', 
                    'opr', 'epa_current', 'epa_recent', 'epa_mean', 'epa_max',
                    'wins', 'losses', 'ties', 'win_rate'
                ]
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                    
                def get_numeric(val):
                    if isinstance(val, (int, float)):
                        return val
                    elif isinstance(val, dict):
                        return val.get('current', 0)
                    return 0
                    
                # Sort teams by current EPA safely
                sorted_teams = sorted(
                    team_data.items(),
                    key=lambda x: get_numeric(x[1]['epa_current']),
                    reverse=True
                )
                    
                for team, data in sorted_teams:
                    writer.writerow({
                        'team': team,
                        'nickname': data['nickname'],
                        'city': data['city'],
                        'state': data['state_prov'],
                        'country': data['country'],
                        'opr': data['opr'],
                        'epa_current': get_numeric(data['epa_current']),
                        'epa_recent': data['epa_recent'],
                        'epa_mean': data['epa_mean'],
                        'epa_max': data['epa_max'],
                        'wins': data['wins'],
                        'losses': data['losses'],
                        'ties': data['ties'],
                        'win_rate': data['win_rate']
                    })
                
            all_csv_files.append(batch_csv_file)
            progress = 40 + (i + len(batch)) / len(teams) * 40
            self.progress_signal.emit(progress)
        
        # Combine all batch CSV files into a single CSV
        combined_csv_file = os.path.join(self.output_dir, "All_Team_Insights.csv")
        fieldnames = set()
        rows = []
        for csv_path in all_csv_files:
            with open(csv_path, 'r', newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                fieldnames.update(reader.fieldnames)
                rows.extend(list(reader))
        fieldnames = list(fieldnames)

        # Write one combined CSV
        with open(combined_csv_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for row in rows:
                writer.writerow(row)
        all_csv_files.append(combined_csv_file)

        result = {
            'csv_files': all_csv_files,
            'output_dir': self.output_dir
        }
            
        self.result_signal.emit(result)
        self.progress_signal.emit(100)


class ScoutingApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("FEDS Scouting Suite")
        self.resize(900, 700)
        
        # Initialize clients
        self.tba_client = BlueAllianceClient()
        self.statbotics_client = StatboticsClient()
        self.statbotics_client.tba = self.tba_client  # Set TBA reference
        
        # Create main widget and layout
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        
        self.main_layout = QVBoxLayout(self.central_widget)
        
        # Create tab widget
        self.tab_widget = QTabWidget()
        self.main_layout.addWidget(self.tab_widget)
        
        # Create tabs
        self.tba_tab = QWidget()
        self.stats_tab = QWidget()
        
        self.tab_widget.addTab(self.tba_tab, "Blue Alliance Data")
        self.tab_widget.addTab(self.stats_tab, "Match Statistics")
        
        # Initialize tabs
        self.init_tba_tab()
        self.init_stats_tab()
        
        # Load saved settings
        self.load_saved_settings()

    def init_tba_tab(self):
        """Initialize the Blue Alliance tab."""
        layout = QVBoxLayout(self.tba_tab)
        
        # Title
        title_label = QLabel("Blue Alliance Data Converter")
        title_label.setFont(QFont('Segoe UI', 16, QFont.Bold))
        layout.addWidget(title_label)
        
        # API Key frame
        api_frame = QHBoxLayout()
        api_label = QLabel("TBA API Key:")
        self.tba_api_key_entry = QLineEdit()
        api_frame.addWidget(api_label)
        api_frame.addWidget(self.tba_api_key_entry)
        layout.addLayout(api_frame)
        
        # Event key frame
        event_frame = QHBoxLayout()
        event_label = QLabel("Event Key:")
        self.tba_event_key_entry = QLineEdit()
        event_help = QLabel("(e.g., 2023miliv)")
        event_frame.addWidget(event_label)
        event_frame.addWidget(self.tba_event_key_entry)
        event_frame.addWidget(event_help)
        layout.addLayout(event_frame)
        
        # Output directory frame
        output_frame = QHBoxLayout()
        output_label = QLabel("Output Directory:")
        self.tba_output_dir_entry = QLineEdit(os.path.join(os.path.dirname(__file__), "tba_data"))
        browse_button = QPushButton("Browse")
        browse_button.clicked.connect(self.tba_browse_directory)
        output_frame.addWidget(output_label)
        output_frame.addWidget(self.tba_output_dir_entry)
        output_frame.addWidget(browse_button)
        layout.addLayout(output_frame)
        
        # Update existing data option
        self.tba_update_existing = QCheckBox("Update existing files (don't create new folder)")
        self.tba_update_existing.setChecked(True)
        layout.addWidget(self.tba_update_existing)
        
        # Fetch button
        fetch_button = QPushButton("Fetch and Convert TBA Data")
        fetch_button.clicked.connect(self.tba_fetch_and_convert)
        layout.addWidget(fetch_button)
        
        # Status label
        self.tba_status_label = QLabel()
        self.tba_status_label.setStyleSheet("color: blue;")
        layout.addWidget(self.tba_status_label)
        
        # Progress bar
        self.tba_progress = QProgressBar()
        self.tba_progress.setRange(0, 100)
        layout.addWidget(self.tba_progress)
        
        # Results frame
        self.tba_results_frame = QFrame()
        self.tba_results_frame.setFrameShape(QFrame.StyledPanel)
        self.tba_results_layout = QVBoxLayout(self.tba_results_frame)
        layout.addWidget(self.tba_results_frame)

    def init_stats_tab(self):
        """Initialize the Statistics tab."""
        layout = QVBoxLayout(self.stats_tab)
        
        # Title
        title_label = QLabel("Combined Match Statistics")
        title_label.setFont(QFont('Segoe UI', 16, QFont.Bold))
        layout.addWidget(title_label)
        
        # Event key frame
        event_frame = QHBoxLayout()
        event_label = QLabel("Event Key:")
        self.stats_event_key_entry = QLineEdit()
        event_help = QLabel("(e.g., 2025miket)")
        event_frame.addWidget(event_label)
        event_frame.addWidget(self.stats_event_key_entry)
        event_frame.addWidget(event_help)
        layout.addLayout(event_frame)
        
        # Match key frame
        match_frame = QHBoxLayout()
        match_label = QLabel("Match Number:")
        self.stats_match_number_entry = QLineEdit()
        match_help = QLabel("(e.g., qm1, sf2m3)")
        match_frame.addWidget(match_label)
        match_frame.addWidget(self.stats_match_number_entry)
        match_frame.addWidget(match_help)
        layout.addLayout(match_frame)
        
        # Match type frame
        match_type_frame = QHBoxLayout()
        match_type_label = QLabel("Match Type:")
        self.stats_match_type_combo = QComboBox()
        self.stats_match_type_combo.addItems(["qm", "sf", "f", "qf"])
        match_type_frame.addWidget(match_type_label)
        match_type_frame.addWidget(self.stats_match_type_combo)
        layout.addLayout(match_type_frame)
        
        # Output directory frame
        output_frame = QHBoxLayout()
        output_label = QLabel("Output Directory:")
        self.stats_output_dir_entry = QLineEdit(os.path.join(os.path.dirname(__file__), "match_stats"))
        browse_button = QPushButton("Browse")
        browse_button.clicked.connect(self.stats_browse_directory)
        output_frame.addWidget(output_label)
        output_frame.addWidget(self.stats_output_dir_entry)
        output_frame.addWidget(browse_button)
        layout.addLayout(output_frame)
        
        # TBA API Key frame
        api_frame = QHBoxLayout()
        api_label = QLabel("TBA API Key:")
        self.stats_api_key_entry = QLineEdit()
        api_frame.addWidget(api_label)
        api_frame.addWidget(self.stats_api_key_entry)
        layout.addLayout(api_frame)
        
        # Button frame
        button_frame = QHBoxLayout()
        fetch_button = QPushButton("Fetch Match Data")
        fetch_button.clicked.connect(self.fetch_combined_match_data)
        team_insights_button = QPushButton("Generate Team Insights")
        team_insights_button.clicked.connect(self.generate_team_insights)
        button_frame.addWidget(fetch_button)
        button_frame.addWidget(team_insights_button)
        layout.addLayout(button_frame)
        
        # Status label
        self.stats_status_label = QLabel()
        self.stats_status_label.setStyleSheet("color: blue;")
        layout.addWidget(self.stats_status_label)
        
        # Progress bar
        self.stats_progress = QProgressBar()
        self.stats_progress.setRange(0, 100)
        layout.addWidget(self.stats_progress)
        
        # Results frame
        self.stats_results_frame = QFrame()
        self.stats_results_frame.setFrameShape(QFrame.StyledPanel)
        self.stats_results_layout = QVBoxLayout(self.stats_results_frame)
        layout.addWidget(self.stats_results_frame)

    def stats_browse_directory(self):
        directory = QFileDialog.getExistingDirectory(self, "Select Output Directory")
        if directory:
            self.stats_output_dir_entry.setText(directory)

    def tba_browse_directory(self):
        directory = QFileDialog.getExistingDirectory(self, "Select Output Directory")
        if directory:
            self.tba_output_dir_entry.setText(directory)

    def load_saved_settings(self):
        """Load saved settings if available."""
        try:
            if os.path.exists('scouting_config.json'):
                with open('scouting_config.json', 'r') as f:
                    config = json.load(f)
                    # TBA settings
                    if 'tba_api_key' in config:
                        self.tba_api_key_entry.setText(config['tba_api_key'])
                        self.stats_api_key_entry.setText(config['tba_api_key'])  # Share API key between tabs
                    if 'tba_event_key' in config:
                        self.tba_event_key_entry.setText(config['tba_event_key'])
                        self.stats_event_key_entry.setText(config['tba_event_key'])  # Share event key between tabs
                    if 'tba_output_dir' in config:
                        self.tba_output_dir_entry.setText(config['tba_output_dir'])
                        
                    # Stats settings
                    if 'stats_output_dir' in config:
                        self.stats_output_dir_entry.setText(config['stats_output_dir'])
        except Exception as e:
            print(f"Error loading saved settings: {e}")

    def save_settings(self):
        """Save settings for future use."""
        try:
            config = {
                'tba_api_key': self.tba_api_key_entry.text(),
                'tba_event_key': self.tba_event_key_entry.text(),
                'tba_output_dir': self.tba_output_dir_entry.text(),
                'stats_output_dir': self.stats_output_dir_entry.text()
            }
            with open('scouting_config.json', 'w') as f:
                json.dump(config, f)
        except Exception as e:
            print(f"Error saving settings: {e}")

    def tba_fetch_and_convert(self):
        """Fetch and convert TBA data."""
        api_key = self.tba_api_key_entry.text().strip()
        event_key = self.tba_event_key_entry.text().strip()
        output_dir = self.tba_output_dir_entry.text().strip()
        update_existing = self.tba_update_existing.isChecked()
        
        # Validate inputs
        if not api_key:
            QMessageBox.critical(self, "Error", "Please enter a TBA API key")
            return
            
        if not event_key:
            QMessageBox.critical(self, "Error", "Please enter an event key")
            return
        
        # Save settings for future use
        self.save_settings()
        
        # Update client API key
        self.tba_client.headers["X-TBA-Auth-Key"] = api_key
        
        # Clear previous results
        self.clear_layout(self.tba_results_layout)
        
        # Create and start the thread
        self.tba_thread = FetchDataThread(self.tba_client, event_key, output_dir, update_existing)
        self.tba_thread.progress_signal.connect(self.tba_progress.setValue)
        self.tba_thread.status_signal.connect(self.tba_status_label.setText)
        self.tba_thread.result_signal.connect(self.handle_tba_thread_result)
        self.tba_thread.error_signal.connect(self.handle_tba_thread_error)
        self.tba_thread.start()
        self.tba_progress.setValue(0)

    def handle_tba_thread_result(self, result):
        """Handle the result of the TBA data fetch thread."""
        self.tba_status_label.setText("Data fetch and conversion completed successfully!")
        self.tba_progress.setValue(100)
        
        # Display results
        result_label = QLabel(f"Data saved in: {result['event_dir']}")
        self.tba_results_layout.addWidget(result_label)
        for csv_file in result['csv_files']:
            file_label = QLabel(f"CSV File: {csv_file}")
            self.tba_results_layout.addWidget(file_label)

    def handle_tba_thread_error(self, error_message):
        """Handle errors from the TBA data fetch thread."""
        self.tba_status_label.setText(f"Error: {error_message}")
        QMessageBox.critical(self, "Error", error_message)

    def clear_layout(self, layout):
        """Clear all widgets from a layout."""
        while layout.count():
            child = layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

    def fetch_combined_match_data(self):
        """Fetch combined match data from TBA and Statbotics."""
        api_key = self.stats_api_key_entry.text().strip()
        event_key = self.stats_event_key_entry.text().strip()
        match_number = self.stats_match_number_entry.text().strip()
        match_type = self.stats_match_type_combo.currentText().strip()
        output_dir = self.stats_output_dir_entry.text().strip()
        
        # Validate inputs
        if not api_key:
            QMessageBox.critical(self, "Error", "Please enter a TBA API key")
            return
            
        if not event_key:
            QMessageBox.critical(self, "Error", "Please enter an event key")
            return
            
        if not match_number:
            QMessageBox.critical(self, "Error", "Please enter a match number")
            return
        
        # Save settings for future use
        self.save_settings()
        
        # Update client API key
        self.tba_client.headers["X-TBA-Auth-Key"] = api_key
        
        # Clear previous results
        self.clear_layout(self.stats_results_layout)
        
        # Create and start the thread
        self.match_thread = FetchMatchDataThread(self, event_key, match_type, match_number, output_dir)
        self.match_thread.progress_signal.connect(self.stats_progress.setValue)
        self.match_thread.status_signal.connect(self.stats_status_label.setText)
        self.match_thread.result_signal.connect(self.handle_match_thread_result)
        self.match_thread.error_signal.connect(self.handle_match_thread_error)
        self.match_thread.start()
        self.stats_progress.setValue(0)

    def handle_match_thread_result(self, result):
        """Handle the result of the match data fetch thread."""
        self.stats_status_label.setText("Match data fetch and combination completed successfully!")
        self.stats_progress.setValue(100)
        
        # Display results
        result_label = QLabel(f"Combined data saved in: {result['output_filename']}")
        self.stats_results_layout.addWidget(result_label)

    def handle_match_thread_error(self, error_message):
        """Handle errors from the match data fetch thread."""
        self.stats_status_label.setText(f"Error: {error_message}")
        QMessageBox.critical(self, "Error", error_message)

    def generate_team_insights(self):
        """Generate team insights for the event."""
        api_key = self.stats_api_key_entry.text().strip()
        event_key = self.stats_event_key_entry.text().strip()
        output_dir = self.stats_output_dir_entry.text().strip()
        
        # Validate inputs
        if not api_key:
            QMessageBox.critical(self, "Error", "Please enter a TBA API key")
            return
            
        if not event_key:
            QMessageBox.critical(self, "Error", "Please enter an event key")
            return
        
        # Save settings for future use
        self.save_settings()
        
        # Update client API key
        self.tba_client.headers["X-TBA-Auth-Key"] = api_key
        
        # Clear previous results
        self.clear_layout(self.stats_results_layout)
        
        # Create and start the thread
        self.insights_thread = FetchTeamInsightsThread(self, event_key, output_dir)
        self.insights_thread.progress_signal.connect(self.stats_progress.setValue)
        self.insights_thread.status_signal.connect(self.stats_status_label.setText)
        self.insights_thread.result_signal.connect(self.handle_insights_thread_result)
        self.insights_thread.error_signal.connect(self.handle_insights_thread_error)
        self.insights_thread.start()
        self.stats_progress.setValue(0)

    def handle_insights_thread_result(self, result):
        """Handle the result of the team insights fetch thread."""
        self.stats_status_label.setText("Team insights generation completed successfully!")
        self.stats_progress.setValue(100)
        
        # Display results
        # Access the first CSV file in the list, if available
        if result.get('csv_files'):
            result_label = QLabel(f"Team insights saved in: {result['csv_files'][0]}")
        else:
            result_label = QLabel(f"Team insights saved in: {result['output_dir']}")
        self.stats_results_layout.addWidget(result_label)

    def handle_insights_thread_error(self, error_message):
        """Handle errors from the team insights fetch thread."""
        self.stats_status_label.setText(f"Error: {error_message}")
        QMessageBox.critical(self, "Error", error_message)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ScoutingApp()
    window.show()
    sys.exit(app.exec_())