from src.cuga.modular.tools.sales.outreach.email_provider import send_email
from src.cuga.modular.tools.sales.outreach.calendar_provider import create_event
from src.cuga.modular.tools.sales.outreach.sequencer import SequenceManager
import pytest

@pytest.fixture
def setup_outreach_tools():
    # Setup code for outreach tools
    email_provider = send_email
    calendar_provider = create_event
    sequencer = SequenceManager()
    return email_provider, calendar_provider, sequencer

def test_send_email(setup_outreach_tools):
    email_provider, _, _ = setup_outreach_tools
    response = email_provider("test@example.com", "Subject", "Body")
    assert response.status_code == 200  # Assuming a successful response returns 200

def test_create_event(setup_outreach_tools):
    _, calendar_provider, _ = setup_outreach_tools
    response = calendar_provider("Meeting", "2023-10-01T10:00:00Z", "2023-10-01T11:00:00Z")
    assert response.status_code == 200  # Assuming a successful response returns 200

def test_sequence_manager(setup_outreach_tools):
    _, _, sequencer = setup_outreach_tools
    sequencer.add_step("Step 1")
    sequencer.add_step("Step 2")
    assert sequencer.get_steps() == ["Step 1", "Step 2"]  # Check if steps are added correctly

def test_sequence_execution(setup_outreach_tools):
    _, _, sequencer = setup_outreach_tools
    sequencer.add_step("Step 1")
    sequencer.execute()
    assert sequencer.current_step == "Step 2"  # Assuming it moves to the next step after execution