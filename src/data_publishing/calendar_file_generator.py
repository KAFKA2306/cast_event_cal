import csv
from ics import Calendar, Event

class CalendarFileGenerator:
    def __init__(self, config_manager, logger=None):
        self.config_manager = config_manager
        self.logger = logger

    def generate_calendar_files(self, events):
        """
        Generate calendar files in CSV and ICS formats.
        """
        self.generate_csv(events)
        self.generate_ics(events)

    def generate_csv(self, events):
        """Generate a Google Calendar-compatible CSV file."""
        filename = "data/published_outputs/google_calendar_export.csv"
        try:
            with open(filename, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(['Subject', 'Start Date', 'Start Time', 'End Date', 'End Time', 'Description', 'Location'])
                for event in events:
                    writer.writerow([event['event_name'], event['date_time'], '', event['date_time'], '', event['description'], event['location']])
            print(f"CSV file generated: {filename}")
        except Exception as e:
            print(f"Error generating CSV file: {e}")
            writer = csv.writer(csvfile)
            writer.writerow(['Subject', 'Start Date', 'Start Time', 'End Date', 'End Time', 'Description', 'Location'])
            for event in events:
                writer.writerow([event['event_name'], event['date_time'], '', event['date_time'], '', event['description'], event['location']])
        print(f"CSV file generated: {filename}")

    def generate_ics(self, events):
        """Generate an iCalendar (.ics) file."""
        calendar = Calendar()
        for event_data in events:
            event = Event()
            event.name = event_data['event_name']
            event.begin = event_data['date_time']
            event.description = event_data['description']
            event.location = event_data['location']
            calendar.events.add(event)

        filename = "data/published_outputs/events.ics"
        try:
            with open(filename, 'w') as f:
                f.writelines(calendar.serialize_iter())
            print(f"ICS file generated: {filename}")
        except Exception as e:
            print(f"Error generating ICS file: {e}")
