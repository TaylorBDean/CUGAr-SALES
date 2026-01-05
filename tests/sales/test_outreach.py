"""
Tests for Domain 3: Outreach & Personalization capabilities.

Coverage:
- draft_outbound_message: Template rendering, variable substitution, validation
- assess_message_quality: Quality scoring, issue detection, improvement suggestions
- manage_template_library: CRUD operations, template storage
"""

import pytest
from cuga.modular.tools.sales.outreach import (
    draft_outbound_message,
    assess_message_quality,
    manage_template_library,
    MessageChannel,
    MessageQualityIssue,
)


# Test Context
CONTEXT = {"trace_id": "test-trace-123", "profile": "sales"}


class TestDraftOutboundMessage:
    """Test message drafting with template rendering and personalization."""
    
    def test_basic_template_rendering(self):
        """Should substitute variables in template."""
        result = draft_outbound_message(
            inputs={
                "template": "Hi {{first_name}}, I noticed {{company}} is in {{industry}}.",
                "prospect_data": {
                    "first_name": "Jane",
                    "company": "Acme Corp",
                    "industry": "Technology",
                },
                "channel": "email",
            },
            context=CONTEXT,
        )
        
        assert result["status"] == "draft"
        assert "Jane" in result["message_draft"]
        assert "Acme Corp" in result["message_draft"]
        assert "Technology" in result["message_draft"]
        assert "{{" not in result["message_draft"]  # No unsubstituted variables
        assert set(result["variables_used"]) == {"first_name", "company", "industry"}
        assert result["missing_variables"] == []
    
    def test_missing_variables_detection(self):
        """Should identify missing template variables."""
        result = draft_outbound_message(
            inputs={
                "template": "Hi {{first_name}}, I saw {{company}} raised {{funding_amount}}.",
                "prospect_data": {
                    "first_name": "John",
                    # Missing: company, funding_amount
                },
                "channel": "email",
            },
            context=CONTEXT,
        )
        
        assert result["status"] == "draft"
        assert "John" in result["message_draft"]
        assert "{{company}}" in result["message_draft"]  # Unsubstituted
        assert "{{funding_amount}}" in result["message_draft"]  # Unsubstituted
        assert result["variables_used"] == ["first_name"]
        assert set(result["missing_variables"]) == {"company", "funding_amount"}
    
    def test_subject_line_extraction_email(self):
        """Should extract subject line from first line for email."""
        result = draft_outbound_message(
            inputs={
                "template": "Quick question about {{topic}}\n\nHi {{first_name}}, ...",
                "prospect_data": {
                    "topic": "AI adoption",
                    "first_name": "Sarah",
                },
                "channel": "email",
            },
            context=CONTEXT,
        )
        
        assert result["subject"] == "Quick question about AI adoption"
        assert "Hi Sarah" in result["message_draft"]
        assert "Quick question" not in result["message_draft"]  # Removed from body
    
    def test_personalization_score_calculation(self):
        """Should calculate personalization score based on variable usage."""
        # High personalization (all variables provided)
        high_result = draft_outbound_message(
            inputs={
                "template": "Hi {{name}}, congrats on {{achievement}}!",
                "prospect_data": {"name": "Alex", "achievement": "Series B funding"},
                "channel": "linkedin",
            },
            context=CONTEXT,
        )
        
        assert high_result["metadata"]["personalization_score"] == 1.0  # 2/2 vars
        
        # Low personalization (missing variables)
        low_result = draft_outbound_message(
            inputs={
                "template": "Hi {{name}}, congrats on {{achievement}}!",
                "prospect_data": {"name": "Alex"},  # Missing achievement
                "channel": "linkedin",
            },
            context=CONTEXT,
        )
        
        assert low_result["metadata"]["personalization_score"] == 0.5  # 1/2 vars
    
    def test_word_count_tracking(self):
        """Should track word count in metadata."""
        result = draft_outbound_message(
            inputs={
                "template": "Hi {{name}}, this is a test message with exactly ten words here.",
                "prospect_data": {"name": "Test"},
                "channel": "email",
            },
            context=CONTEXT,
        )
        
        # "Hi Test, this is a test message with exactly ten words here." = 12 words
        assert result["metadata"]["word_count"] == 12
    
    def test_no_auto_send_status(self):
        """Should always return 'draft' status, never 'sent'."""
        result = draft_outbound_message(
            inputs={
                "template": "Hi {{name}}",
                "prospect_data": {"name": "Test"},
                "channel": "email",
            },
            context=CONTEXT,
        )
        
        assert result["status"] == "draft"
        assert result["status"] != "sent"  # Safety check
    
    def test_multiple_channels_supported(self):
        """Should support all message channels."""
        for channel in ["email", "linkedin", "phone", "sms"]:
            result = draft_outbound_message(
                inputs={
                    "template": "Hi {{name}}",
                    "prospect_data": {"name": "Test"},
                    "channel": channel,
                },
                context=CONTEXT,
            )
            
            assert result["status"] == "draft"
            assert result["channel"] == channel
    
    def test_empty_template_error(self):
        """Should return error for empty template."""
        result = draft_outbound_message(
            inputs={
                "template": "",
                "prospect_data": {"name": "Test"},
                "channel": "email",
            },
            context=CONTEXT,
        )
        
        assert result["status"] == "error"
        assert "required" in result["error"].lower()


class TestAssessMessageQuality:
    """Test message quality assessment and issue detection."""
    
    def test_high_quality_message_grade_a(self):
        """Should assign A grade to high-quality personalized message."""
        result = assess_message_quality(
            inputs={
                "message": "Hi Jane, I noticed Acme Corp recently launched a new product line. "
                          "Congrats on the growth! I work with tech companies scaling their sales "
                          "operations. Would you be open to a 15-minute call next week?",
                "subject": "Congrats on your product launch",
                "channel": "email",
            },
            context=CONTEXT,
        )
        
        assert result["quality_grade"] in ["A", "B"]  # High quality
        assert result["overall_score"] >= 0.8
        assert result["ready_to_send"] is True
        assert result["metrics"]["personalization_detected"] is True
        assert result["metrics"]["call_to_action_detected"] is True
        assert len(result["strengths"]) > 0
    
    def test_low_quality_generic_message(self):
        """Should flag generic messages with multiple issues."""
        result = assess_message_quality(
            inputs={
                "message": "Hi, I hope this email finds you well. Our product is great. "
                          "You should buy it immediately. What do you think? When can we talk? "
                          "What's your budget? Can you decide now?",
                "subject": "Hi",
                "channel": "email",
            },
            context=CONTEXT,
        )
        
        # Should detect multiple issues (3-4 warnings)
        issue_types = [issue["issue_type"] for issue in result["issues"]]
        
        # Must detect these specific issues
        assert MessageQualityIssue.MULTIPLE_ASKS.value in issue_types
        assert MessageQualityIssue.WEAK_SUBJECT.value in issue_types
        assert MessageQualityIssue.GENERIC_OPENING.value in issue_types
        
        # Should have multiple warnings
        assert len(result["issues"]) >= 3
        
        # Overall score should be degraded due to warnings
        assert result["overall_score"] <= 0.9  # Not perfect quality
    
    def test_broken_template_variables_critical_issue(self):
        """Should flag unsubstituted template variables as critical."""
        result = assess_message_quality(
            inputs={
                "message": "Hi {{first_name}}, I noticed {{company}} is growing. Can we chat?",
                "subject": "Quick question",
                "channel": "email",
            },
            context=CONTEXT,
        )
        
        assert result["ready_to_send"] is False
        issue_types = [issue["issue_type"] for issue in result["issues"]]
        assert MessageQualityIssue.BROKEN_VARIABLE.value in issue_types
        
        # Critical issues should have high severity
        broken_var_issue = next(
            (i for i in result["issues"] if i["issue_type"] == MessageQualityIssue.BROKEN_VARIABLE.value),
            None
        )
        assert broken_var_issue is not None
        assert broken_var_issue["severity"] == "critical"
    
    def test_message_length_warnings(self):
        """Should warn on too-short or too-long messages."""
        # Too short
        short_result = assess_message_quality(
            inputs={
                "message": "Hi Jane, interested?",
                "subject": "Question",
                "channel": "email",
            },
            context=CONTEXT,
        )
        
        issue_types_short = [issue["issue_type"] for issue in short_result["issues"]]
        assert MessageQualityIssue.TOO_SHORT.value in issue_types_short
        
        # Too long (>200 words)
        long_message = "Hi Jane, " + " ".join(["word"] * 250)
        long_result = assess_message_quality(
            inputs={
                "message": long_message,
                "subject": "Long message",
                "channel": "email",
            },
            context=CONTEXT,
        )
        
        issue_types_long = [issue["issue_type"] for issue in long_result["issues"]]
        assert MessageQualityIssue.TOO_LONG.value in issue_types_long
    
    def test_subject_line_length_validation(self):
        """Should validate subject line length for email."""
        # Too short subject
        short_result = assess_message_quality(
            inputs={
                "message": "Hi Jane, can we chat about your sales process?",
                "subject": "Hi",
                "channel": "email",
            },
            context=CONTEXT,
        )
        
        issue_types = [issue["issue_type"] for issue in short_result["issues"]]
        assert MessageQualityIssue.WEAK_SUBJECT.value in issue_types
        
        # Too long subject
        long_result = assess_message_quality(
            inputs={
                "message": "Hi Jane, can we chat about your sales process?",
                "subject": "This is a very long subject line with way too many words that will get truncated",
                "channel": "email",
            },
            context=CONTEXT,
        )
        
        issue_types = [issue["issue_type"] for issue in long_result["issues"]]
        assert MessageQualityIssue.WEAK_SUBJECT.value in issue_types
    
    def test_no_call_to_action_critical(self):
        """Should flag missing call-to-action as critical."""
        result = assess_message_quality(
            inputs={
                "message": "Hi Jane, I noticed Acme Corp is growing fast. "
                          "We help companies like yours scale operations.",
                "subject": "Congrats on growth",
                "channel": "email",
            },
            context=CONTEXT,
        )
        
        assert result["ready_to_send"] is False
        issue_types = [issue["issue_type"] for issue in result["issues"]]
        assert MessageQualityIssue.NO_CALL_TO_ACTION.value in issue_types
    
    def test_pushy_tone_detection(self):
        """Should detect pushy language."""
        result = assess_message_quality(
            inputs={
                "message": "Hi Jane, you need to act immediately! "
                          "This is urgent and you must decide ASAP. "
                          "You should not wait.",
                "subject": "Urgent action required",
                "channel": "email",
            },
            context=CONTEXT,
        )
        
        issue_types = [issue["issue_type"] for issue in result["issues"]]
        assert MessageQualityIssue.PUSHY_TONE.value in issue_types
    
    def test_metrics_calculation(self):
        """Should calculate message metrics correctly."""
        result = assess_message_quality(
            inputs={
                "message": "Hi Jane, I noticed Acme Corp is growing. Can we chat?",
                "subject": "Quick question",
                "channel": "email",
            },
            context=CONTEXT,
        )
        
        metrics = result["metrics"]
        assert metrics["word_count"] == 11  # Actual word count
        assert metrics["sentence_count"] == 2
        assert metrics["avg_sentence_length"] == 5.5  # 11 words / 2 sentences
        assert isinstance(metrics["personalization_detected"], bool)
        assert isinstance(metrics["call_to_action_detected"], bool)
    
    def test_empty_message_error(self):
        """Should return error for empty message."""
        result = assess_message_quality(
            inputs={
                "message": "",
                "subject": "Test",
                "channel": "email",
            },
            context=CONTEXT,
        )
        
        assert result["status"] == "error"
        assert "required" in result["error"].lower()


class TestManageTemplateLibrary:
    """Test template library CRUD operations."""
    
    def test_list_templates(self):
        """Should return list of available templates."""
        result = manage_template_library(
            inputs={"operation": "list"},
            context=CONTEXT,
        )
        
        assert result["status"] == "success"
        assert result["operation"] == "list"
        assert "templates" in result
        assert isinstance(result["templates"], list)
        assert result["count"] >= 0
        
        # Check template structure
        if result["templates"]:
            template = result["templates"][0]
            assert "template_id" in template
            assert "name" in template
            assert "template" in template
            assert "channel" in template
            assert "category" in template
    
    def test_read_template(self):
        """Should retrieve specific template by ID."""
        result = manage_template_library(
            inputs={
                "operation": "read",
                "template_id": "tech_prospecting_v1",
            },
            context=CONTEXT,
        )
        
        assert result["status"] == "success"
        assert result["operation"] == "read"
        assert result["template_id"] == "tech_prospecting_v1"
        assert "template" in result
    
    def test_create_template(self):
        """Should create new template and return ID."""
        result = manage_template_library(
            inputs={
                "operation": "create",
                "template_data": {
                    "name": "Test Template",
                    "template": "Hi {{name}}, this is a test.",
                    "channel": "email",
                    "category": "prospecting",
                },
            },
            context=CONTEXT,
        )
        
        assert result["status"] == "success"
        assert result["operation"] == "create"
        assert "template_id" in result
        assert result["template_id"].startswith("test_template_")
    
    def test_update_template(self):
        """Should update existing template."""
        result = manage_template_library(
            inputs={
                "operation": "update",
                "template_id": "tech_prospecting_v1",
                "template_data": {
                    "name": "Updated Template",
                    "template": "Hi {{name}}, updated content.",
                },
            },
            context=CONTEXT,
        )
        
        assert result["status"] == "success"
        assert result["operation"] == "update"
        assert result["template_id"] == "tech_prospecting_v1"
    
    def test_delete_template(self):
        """Should delete template by ID."""
        result = manage_template_library(
            inputs={
                "operation": "delete",
                "template_id": "tech_prospecting_v1",
            },
            context=CONTEXT,
        )
        
        assert result["status"] == "success"
        assert result["operation"] == "delete"
        assert result["template_id"] == "tech_prospecting_v1"
    
    def test_missing_template_id_for_read(self):
        """Should return error when template_id missing for read."""
        result = manage_template_library(
            inputs={"operation": "read"},
            context=CONTEXT,
        )
        
        assert result["status"] == "error"
        assert "template_id" in result["message"].lower()
    
    def test_missing_data_for_create(self):
        """Should return error when template_data missing required fields."""
        result = manage_template_library(
            inputs={
                "operation": "create",
                "template_data": {"name": "Test"},  # Missing template
            },
            context=CONTEXT,
        )
        
        assert result["status"] == "error"
        assert "required" in result["message"].lower()
    
    def test_unknown_operation_error(self):
        """Should return error for unknown operation."""
        result = manage_template_library(
            inputs={"operation": "invalid_operation"},
            context=CONTEXT,
        )
        
        assert result["status"] == "error"
        assert "unknown operation" in result["message"].lower()


class TestOutreachIntegration:
    """Integration tests combining multiple outreach capabilities."""
    
    def test_draft_and_assess_workflow(self):
        """Should draft message then assess quality."""
        # Step 1: Draft message
        draft_result = draft_outbound_message(
            inputs={
                "template": "Quick question about {{topic}}\n\n"
                           "Hi {{first_name}}, I noticed {{company}} recently {{activity}}. "
                           "Congrats on the progress! I work with {{industry}} companies "
                           "optimizing their {{pain_point}} processes. "
                           "Would you be open to a 15-minute call next week to discuss "
                           "how we've helped similar companies achieve {{benefit}}?",
                "prospect_data": {
                    "topic": "sales efficiency",
                    "first_name": "Sarah",
                    "company": "TechCorp",
                    "activity": "expanded to 3 new markets",
                    "industry": "SaaS",
                    "pain_point": "outbound sales",
                    "benefit": "2x conversion rates",
                },
                "channel": "email",
            },
            context=CONTEXT,
        )
        
        assert draft_result["status"] == "draft"
        assert draft_result["missing_variables"] == []
        assert draft_result["metadata"]["personalization_score"] == 1.0
        
        # Step 2: Assess quality
        assess_result = assess_message_quality(
            inputs={
                "message": draft_result["message_draft"],
                "subject": draft_result["subject"],
                "channel": "email",
            },
            context=CONTEXT,
        )
        
        assert assess_result["ready_to_send"] is True
        assert assess_result["quality_grade"] in ["A", "B"]
        assert assess_result["metrics"]["personalization_detected"] is True
        assert assess_result["metrics"]["call_to_action_detected"] is True
    
    def test_template_library_to_draft_workflow(self):
        """Should retrieve template then use for drafting."""
        # Step 1: List templates
        list_result = manage_template_library(
            inputs={"operation": "list"},
            context=CONTEXT,
        )
        
        assert list_result["status"] == "success"
        assert len(list_result["templates"]) > 0
        
        # Step 2: Use first template for drafting
        template = list_result["templates"][0]
        
        # Extract variables from template
        import re
        template_text = template["template"]
        variables = re.findall(r'\{\{(\w+)\}\}', template_text)
        
        # Provide sample data for variables
        prospect_data = {var: f"sample_{var}" for var in variables}
        
        draft_result = draft_outbound_message(
            inputs={
                "template": template_text,
                "prospect_data": prospect_data,
                "channel": template["channel"],
            },
            context=CONTEXT,
        )
        
        assert draft_result["status"] == "draft"
        assert draft_result["missing_variables"] == []
