event_schema = {
    "type": "object",
    "properties": {
        "event_name": {"type": "string"},
        "date_time": {"type": "string"},
        "organizer": {"type": "string"},
        "location": {"type": "string"},
        "hashtags": {"type": "array", "items": {"type": "string"}}
    },
    "required": ["event_name", "date_time", "organizer", "location"]
}