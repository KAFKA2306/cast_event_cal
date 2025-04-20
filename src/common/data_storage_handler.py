import json

def save_data(data, filename):
    """Saves data to a JSON file."""
    with open(filename, 'w') as f:
        json.dump(data, f)

def load_data(filename):
    """Loads data from a JSON file."""
    try:
        with open(filename, 'r') as f:
            data = json.load(f)
        return data
    except FileNotFoundError:
        return None