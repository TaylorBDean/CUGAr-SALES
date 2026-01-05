from datetime import datetime
from typing import List, Dict, Any

class CalendarProvider:
    def __init__(self, api_client):
        self.api_client = api_client

    def get_events(self, calendar_id: str, time_min: str, time_max: str) -> List[Dict[str, Any]]:
        """
        Retrieve calendar events within a specified time range.

        :param calendar_id: The ID of the calendar to retrieve events from.
        :param time_min: The start time in RFC3339 format.
        :param time_max: The end time in RFC3339 format.
        :return: A list of events.
        """
        events = self.api_client.get_events(calendar_id, time_min, time_max)
        return events.get('items', [])

    def create_event(self, calendar_id: str, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new event in the specified calendar.

        :param calendar_id: The ID of the calendar to create the event in.
        :param event_data: A dictionary containing event details.
        :return: The created event.
        """
        event = self.api_client.create_event(calendar_id, event_data)
        return event

    def update_event(self, calendar_id: str, event_id: str, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update an existing event in the specified calendar.

        :param calendar_id: The ID of the calendar containing the event.
        :param event_id: The ID of the event to update.
        :param event_data: A dictionary containing updated event details.
        :return: The updated event.
        """
        updated_event = self.api_client.update_event(calendar_id, event_id, event_data)
        return updated_event

    def delete_event(self, calendar_id: str, event_id: str) -> None:
        """
        Delete an event from the specified calendar.

        :param calendar_id: The ID of the calendar containing the event.
        :param event_id: The ID of the event to delete.
        """
        self.api_client.delete_event(calendar_id, event_id)