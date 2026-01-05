from cuga.modular.tools.sales.outreach.email_provider import EmailProvider
from cuga.modular.tools.sales.outreach.calendar_provider import CalendarProvider

class Sequencer:
    def __init__(self, email_provider: EmailProvider, calendar_provider: CalendarProvider):
        self.email_provider = email_provider
        self.calendar_provider = calendar_provider
        self.sequences = {}

    def create_sequence(self, sequence_id: str, steps: list):
        self.sequences[sequence_id] = steps

    def execute_sequence(self, sequence_id: str):
        if sequence_id not in self.sequences:
            raise ValueError("Sequence ID not found.")
        
        for step in self.sequences[sequence_id]:
            self._execute_step(step)

    def _execute_step(self, step):
        if step['type'] == 'email':
            self.email_provider.send_email(step['recipient'], step['subject'], step['body'])
        elif step['type'] == 'calendar':
            self.calendar_provider.schedule_event(step['event_details'])
        else:
            raise ValueError("Unknown step type.")

    def get_sequences(self):
        return self.sequences

    def clear_sequences(self):
        self.sequences.clear()