import re
from src.data_processing.text_normalizer import normalize_text

class EventInformationExtractor:
    def __init__(self, config_manager, logger=None):
        self.config_manager = config_manager
        self.logger = logger
        self.config = self.config_manager.get('event_extraction_rules')

    def extract(self, text):
        """
        Extract event information from normalized text using regular expressions,
        keyword matching, etc.
        """
        text = normalize_text(text)

        event_info = {
            "event_name": self.extract_event_name(text),
            "date_time": self.extract_date_time(text),
            "organizer": self.extract_organizer(text),
            "location": self.extract_location(text),
            "hashtags": self.extract_hashtags(text)
        }

        return event_info

    def extract_event_name(self, text):
        # TODO: Implement event name extraction logic here
        return None

    def extract_date_time(self, text):
        # TODO: Implement date and time extraction logic here
        return None

    def extract_organizer(self, text):
        # TODO: Implement organizer extraction logic here
        return None

    def extract_location(self, text):
        # TODO: Implement location extraction logic here
        return None

    def extract_hashtags(self, text):
        hashtags = re.findall(r"#\w+", text)
        return hashtags
