# src/data_integration/recurring_event_handler.py
class RecurringEventHandler:
    def __init__(self, config_manager):
        self.config_manager = config_manager

    def handle_recurring_events(self, events):
        return events