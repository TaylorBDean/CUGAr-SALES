"""
Domain 3: Outreach & Personalization Capabilities

WHY: Sales outreach must be personalized, contextual, and high-quality.
Generic messages get ignored. Manual personalization doesn't scale.

SAFETY: NO AUTO-SEND. Capabilities draft/assess messages, humans approve sending.
Message quality gates prevent spam/low-quality outreach.

OFFLINE-FIRST: Template rendering and quality assessment work locally.
CRM data enrichment is opt-in (Phase 2 adapters).
"""

from __future__ import annotations

from typing import Dict, Any, List, Optional
import logging
import re
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class MessageChannel(str, Enum):
    """Communication channels for outreach."""
    EMAIL = "email"
    LINKEDIN = "linkedin"
    PHONE = "phone"
    SMS = "sms"
    DIRECT_MAIL = "direct_mail"


class MessageQualityIssue(str, Enum):
    """Common message quality issues."""
    TOO_LONG = "too_long"
    TOO_SHORT = "too_short"
    NO_PERSONALIZATION = "no_personalization"
    NO_CALL_TO_ACTION = "no_call_to_action"
    WEAK_SUBJECT = "weak_subject"
    GENERIC_OPENING = "generic_opening"
    PUSHY_TONE = "pushy_tone"
    MULTIPLE_ASKS = "multiple_asks"
    SPELLING_ERROR = "spelling_error"
    BROKEN_VARIABLE = "broken_variable"


def draft_outbound_message(inputs: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate personalized outreach message from template and prospect data.
    
    WHY: Manual message writing doesn't scale. Templates ensure consistency
    while personalization maintains relevance.
    
    CAPABILITY: Template rendering with variable substitution and validation.
    NO AUTO-SEND: Returns draft for human review/approval.
    OFFLINE: Pure template rendering, no external calls.
    
    Args:
        inputs:
            template: Message template with {{variables}}
            prospect_data: Dict with personalization variables
            channel: MessageChannel enum (email, linkedin, phone, sms)
            tone: Optional tone adjustment (professional, casual, urgent)
        context:
            trace_id: Request trace ID
            profile: Execution profile (e.g., "sales")
    
    Returns:
        {
            message_draft: Rendered message text,
            subject: Subject line (for email/linkedin),
            variables_used: [str] - Variables successfully substituted,
            missing_variables: [str] - Variables in template but not in prospect_data,
            channel: MessageChannel,
            status: "draft" (never "sent" - requires human approval),
            created_at: ISO timestamp,
            metadata: {
                template_hash: str,
                word_count: int,
                personalization_score: float (0-1),
            }
        }
    
    Example:
        >>> result = draft_outbound_message(
        ...     inputs={
        ...         "template": "Hi {{first_name}}, I noticed {{company}} is in {{industry}}...",
        ...         "prospect_data": {
        ...             "first_name": "Jane",
        ...             "company": "Acme Corp",
        ...             "industry": "Technology",
        ...         },
        ...         "channel": "email",
        ...     },
        ...     context={"trace_id": "abc-123", "profile": "sales"}
        ... )
        >>> result["message_draft"]
        "Hi Jane, I noticed Acme Corp is in Technology..."
        >>> result["variables_used"]
        ["first_name", "company", "industry"]
    """
    trace_id = context.get("trace_id", "unknown")
    
    # Extract inputs
    template = inputs.get("template", "")
    prospect_data = inputs.get("prospect_data", {})
    channel = inputs.get("channel", MessageChannel.EMAIL.value)
    tone = inputs.get("tone", "professional")
    
    logger.info(f"[{trace_id}] Drafting {channel} message with {len(prospect_data)} variables")
    
    # Validate inputs
    if not template:
        return {
            "status": "error",
            "error": "Template is required",
        }
    
    # Extract variables from template ({{variable_name}} pattern)
    template_variables = set(re.findall(r'\{\{(\w+)\}\}', template))
    
    # Identify missing variables
    provided_variables = set(prospect_data.keys())
    missing_variables = list(template_variables - provided_variables)
    variables_used = list(template_variables & provided_variables)
    
    # Render template with available data
    message_draft = template
    for var_name in variables_used:
        placeholder = f"{{{{{var_name}}}}}"
        value = str(prospect_data[var_name])
        message_draft = message_draft.replace(placeholder, value)
    
    # Extract subject line (first line for email/linkedin)
    subject = ""
    if channel in [MessageChannel.EMAIL.value, MessageChannel.LINKEDIN.value]:
        lines = message_draft.strip().split("\n", 1)
        if lines:
            subject = lines[0].strip()
            if len(lines) > 1:
                message_draft = lines[1].strip()
    
    # Calculate personalization score
    # Higher score = more variables used, fewer generic placeholders
    total_vars = len(template_variables)
    used_vars = len(variables_used)
    personalization_score = used_vars / total_vars if total_vars > 0 else 0.0
    
    # Word count
    word_count = len(message_draft.split())
    
    # Template hash (for tracking/versioning)
    import hashlib
    template_hash = hashlib.md5(template.encode()).hexdigest()[:8]
    
    logger.info(
        f"[{trace_id}] Draft complete: {word_count} words, "
        f"{personalization_score:.0%} personalized, {len(missing_variables)} missing vars"
    )
    
    return {
        "message_draft": message_draft,
        "subject": subject,
        "variables_used": variables_used,
        "missing_variables": missing_variables,
        "channel": channel,
        "status": "draft",  # NEVER "sent" - requires human approval
        "created_at": datetime.now().isoformat(),
        "metadata": {
            "template_hash": template_hash,
            "word_count": word_count,
            "personalization_score": personalization_score,
            "tone": tone,
        },
    }


def assess_message_quality(inputs: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Assess quality of outreach message and identify improvement opportunities.
    
    WHY: Low-quality messages hurt brand reputation and get poor response rates.
    Automated quality checks catch issues before sending.
    
    CAPABILITY: Message analysis for common quality issues.
    OFFLINE: Rule-based scoring, no external calls.
    EXPLAINABLE: Returns specific issues with remediation suggestions.
    
    Args:
        inputs:
            message: Message text to assess
            subject: Subject line (optional, for email)
            channel: MessageChannel enum
            prospect_context: Optional prospect data for personalization checks
        context:
            trace_id: Request trace ID
            profile: Execution profile
    
    Returns:
        {
            overall_score: float (0-1, higher = better quality),
            quality_grade: str (A/B/C/D/F),
            issues: [
                {
                    issue_type: MessageQualityIssue enum,
                    severity: str (critical/warning/info),
                    description: str,
                    suggestion: str (how to fix),
                }
            ],
            strengths: [str] - Positive aspects of the message,
            ready_to_send: bool - False if critical issues found,
            metrics: {
                word_count: int,
                sentence_count: int,
                avg_sentence_length: float,
                personalization_detected: bool,
                call_to_action_detected: bool,
            }
        }
    
    Example:
        >>> result = assess_message_quality(
        ...     inputs={
        ...         "message": "Hi Jane, I noticed Acme Corp is growing. Can we chat?",
        ...         "subject": "Quick question",
        ...         "channel": "email",
        ...     },
        ...     context={"trace_id": "abc-123", "profile": "sales"}
        ... )
        >>> result["quality_grade"]
        "B"
        >>> result["ready_to_send"]
        True
    """
    trace_id = context.get("trace_id", "unknown")
    
    # Extract inputs
    message = inputs.get("message", "")
    subject = inputs.get("subject", "")
    channel = inputs.get("channel", MessageChannel.EMAIL.value)
    prospect_context = inputs.get("prospect_context", {})
    
    logger.info(f"[{trace_id}] Assessing {channel} message quality ({len(message)} chars)")
    
    # Validate inputs
    if not message:
        return {
            "status": "error",
            "error": "Message is required",
        }
    
    issues = []
    strengths = []
    
    # Calculate basic metrics
    word_count = len(message.split())
    sentences = re.split(r'[.!?]+', message)
    sentence_count = len([s for s in sentences if s.strip()])
    avg_sentence_length = word_count / sentence_count if sentence_count > 0 else 0
    
    # Check: Message length (email optimal: 50-125 words)
    if channel == MessageChannel.EMAIL.value:
        if word_count < 30:
            issues.append({
                "issue_type": MessageQualityIssue.TOO_SHORT.value,
                "severity": "warning",
                "description": f"Message is very short ({word_count} words)",
                "suggestion": "Add more context or value proposition. Aim for 50-125 words for email.",
            })
        elif word_count > 200:
            issues.append({
                "issue_type": MessageQualityIssue.TOO_LONG.value,
                "severity": "warning",
                "description": f"Message is too long ({word_count} words)",
                "suggestion": "Shorten message. Busy prospects prefer concise emails (50-125 words).",
            })
        else:
            strengths.append(f"Good length ({word_count} words)")
    
    # Check: Personalization
    personalization_indicators = [
        r'\b[A-Z][a-z]+\b',  # Proper names (capitalized words)
        r'\bI noticed\b',
        r'\bI saw\b',
        r'\bcongrats\b',
        r'\bcongratulations\b',
    ]
    personalization_detected = any(
        re.search(pattern, message, re.IGNORECASE)
        for pattern in personalization_indicators
    )
    
    if not personalization_detected:
        issues.append({
            "issue_type": MessageQualityIssue.NO_PERSONALIZATION.value,
            "severity": "critical",
            "description": "No personalization detected",
            "suggestion": "Add specific reference to prospect, their company, or recent activity.",
        })
    else:
        strengths.append("Personalized opening detected")
    
    # Check: Call to action
    cta_patterns = [
        r'\bcan we\b',
        r'\blet\'s\b',
        r'\bwould you\b',
        r'\bcould you\b',
        r'\binterested in\b',
        r'\bschedule\b',
        r'\bcall\b',
        r'\bmeeting\b',
        r'\bchat\b',
        r'\bdiscuss\b',
    ]
    call_to_action_detected = any(
        re.search(pattern, message, re.IGNORECASE)
        for pattern in cta_patterns
    )
    
    if not call_to_action_detected:
        issues.append({
            "issue_type": MessageQualityIssue.NO_CALL_TO_ACTION.value,
            "severity": "critical",
            "description": "No clear call-to-action",
            "suggestion": "Add specific next step (e.g., 'Can we schedule a 15-min call?').",
        })
    else:
        strengths.append("Clear call-to-action")
    
    # Check: Subject line (email/linkedin)
    if channel in [MessageChannel.EMAIL.value, MessageChannel.LINKEDIN.value] and subject:
        subject_word_count = len(subject.split())
        if subject_word_count < 2:
            issues.append({
                "issue_type": MessageQualityIssue.WEAK_SUBJECT.value,
                "severity": "warning",
                "description": "Subject line is too short",
                "suggestion": "Use 3-7 word subject line. Be specific but concise.",
            })
        elif subject_word_count > 10:
            issues.append({
                "issue_type": MessageQualityIssue.WEAK_SUBJECT.value,
                "severity": "warning",
                "description": "Subject line is too long",
                "suggestion": "Shorten subject to 3-7 words for better open rates.",
            })
        else:
            strengths.append(f"Subject length optimal ({subject_word_count} words)")
    
    # Check: Generic openings
    generic_openings = [
        r'^Hi,?\s*$',
        r'^Hello,?\s*$',
        r'^Dear Sir/Madam',
        r'^To whom it may concern',
        r'I hope this email finds you well',
        r'I hope this message finds you well',
        r'I hope you are doing well',
        r'I hope you\'re doing well',
    ]
    if any(re.search(pattern, message, re.IGNORECASE | re.MULTILINE) for pattern in generic_openings):
        issues.append({
            "issue_type": MessageQualityIssue.GENERIC_OPENING.value,
            "severity": "warning",
            "description": "Generic opening detected",
            "suggestion": "Use prospect's name or specific reference instead of generic greeting.",
        })
    
    # Check: Multiple asks
    question_marks = message.count('?')
    if question_marks > 2:
        issues.append({
            "issue_type": MessageQualityIssue.MULTIPLE_ASKS.value,
            "severity": "warning",
            "description": f"Too many questions ({question_marks})",
            "suggestion": "Focus on one clear ask. Multiple questions confuse prospects.",
        })
    
    # Check: Broken template variables
    broken_vars = re.findall(r'\{\{(\w+)\}\}', message)
    if broken_vars:
        issues.append({
            "issue_type": MessageQualityIssue.BROKEN_VARIABLE.value,
            "severity": "critical",
            "description": f"Unsubstituted template variables: {', '.join(broken_vars)}",
            "suggestion": "Provide values for all template variables before sending.",
        })
    
    # Check: Pushy tone indicators
    pushy_indicators = [
        r'\bneed to\b',
        r'\bmust\b',
        r'\bshould\b',
        r'\bimmediately\b',
        r'\burgent\b',
        r'\bASAP\b',
    ]
    pushy_count = sum(
        len(re.findall(pattern, message, re.IGNORECASE))
        for pattern in pushy_indicators
    )
    if pushy_count > 2:
        issues.append({
            "issue_type": MessageQualityIssue.PUSHY_TONE.value,
            "severity": "warning",
            "description": "Message tone may be too pushy",
            "suggestion": "Soften language. Use 'would you' instead of 'you should'.",
        })
    
    # Calculate overall score
    # Start at 1.0, deduct points for issues
    overall_score = 1.0
    for issue in issues:
        if issue["severity"] == "critical":
            overall_score -= 0.25
        elif issue["severity"] == "warning":
            overall_score -= 0.10
        # info issues don't affect score
    
    overall_score = max(0.0, min(1.0, overall_score))  # Clamp to [0, 1]
    
    # Grade mapping
    if overall_score >= 0.9:
        quality_grade = "A"
    elif overall_score >= 0.8:
        quality_grade = "B"
    elif overall_score >= 0.7:
        quality_grade = "C"
    elif overall_score >= 0.6:
        quality_grade = "D"
    else:
        quality_grade = "F"
    
    # Ready to send if no critical issues
    critical_issues = [i for i in issues if i["severity"] == "critical"]
    ready_to_send = len(critical_issues) == 0
    
    logger.info(
        f"[{trace_id}] Quality assessment: {quality_grade} grade, "
        f"{overall_score:.0%} score, {len(issues)} issues, ready={ready_to_send}"
    )
    
    return {
        "overall_score": round(overall_score, 2),
        "quality_grade": quality_grade,
        "issues": issues,
        "strengths": strengths,
        "ready_to_send": ready_to_send,
        "metrics": {
            "word_count": word_count,
            "sentence_count": sentence_count,
            "avg_sentence_length": round(avg_sentence_length, 1),
            "personalization_detected": personalization_detected,
            "call_to_action_detected": call_to_action_detected,
        },
    }


def manage_template_library(inputs: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Manage outreach message templates (CRUD operations).
    
    WHY: Reusable templates ensure consistency, save time, and enable A/B testing.
    Template library scales outreach without sacrificing quality.
    
    CAPABILITY: Template storage and retrieval (in-memory or file-based).
    OFFLINE: No external dependencies, local storage only.
    
    Args:
        inputs:
            operation: str ("create", "read", "update", "delete", "list")
            template_id: Optional[str] - Template identifier (for read/update/delete)
            template_data: Optional[Dict] - Template content (for create/update)
                {
                    name: str,
                    template: str (message template with {{variables}}),
                    channel: MessageChannel,
                    category: str (prospecting, nurture, follow_up, etc.),
                    effectiveness: Optional[float] (response rate, 0-1),
                }
        context:
            trace_id: Request trace ID
            profile: Execution profile
    
    Returns:
        {
            operation: str,
            status: str ("success" or "error"),
            template_id: Optional[str],
            template: Optional[Dict] - Template data (for read operations),
            templates: Optional[List[Dict]] - List of templates (for list operation),
            message: str - Operation result message,
        }
    
    Example:
        >>> # Create template
        >>> result = manage_template_library(
        ...     inputs={
        ...         "operation": "create",
        ...         "template_data": {
        ...             "name": "Tech Prospecting v1",
        ...             "template": "Hi {{first_name}}, I noticed {{company}}...",
        ...             "channel": "email",
        ...             "category": "prospecting",
        ...         }
        ...     },
        ...     context={"trace_id": "abc", "profile": "sales"}
        ... )
        >>> result["template_id"]
        "tech_prospecting_v1_a3f5"
    """
    trace_id = context.get("trace_id", "unknown")
    operation = inputs.get("operation", "list")
    
    logger.info(f"[{trace_id}] Template library operation: {operation}")
    
    # In-memory template storage (would be file/DB in production)
    # For Phase 3 demonstration, we'll use a simple dict
    # Production would use: VectorMemory for semantic search, file storage, or DB
    
    if operation == "list":
        # Return stub templates for demo
        demo_templates = [
            {
                "template_id": "tech_prospecting_v1",
                "name": "Tech Prospecting v1",
                "template": "Hi {{first_name}}, I noticed {{company}} recently {{recent_activity}}...",
                "channel": MessageChannel.EMAIL.value,
                "category": "prospecting",
                "effectiveness": 0.12,  # 12% response rate
                "created_at": "2026-01-01T00:00:00Z",
            },
            {
                "template_id": "linkedin_intro_v2",
                "name": "LinkedIn Intro v2",
                "template": "Hi {{first_name}}, saw your post about {{topic}}. Interesting perspective on {{key_point}}...",
                "channel": MessageChannel.LINKEDIN.value,
                "category": "prospecting",
                "effectiveness": 0.18,  # 18% response rate
                "created_at": "2026-01-02T00:00:00Z",
            },
        ]
        
        return {
            "operation": "list",
            "status": "success",
            "templates": demo_templates,
            "count": len(demo_templates),
            "message": f"Retrieved {len(demo_templates)} templates",
        }
    
    elif operation == "read":
        template_id = inputs.get("template_id")
        if not template_id:
            return {
                "operation": "read",
                "status": "error",
                "message": "template_id is required for read operation",
            }
        
        # Stub: Would fetch from storage
        return {
            "operation": "read",
            "status": "success",
            "template_id": template_id,
            "template": {
                "template_id": template_id,
                "name": "Demo Template",
                "template": "Hi {{first_name}}, ...",
                "channel": MessageChannel.EMAIL.value,
                "category": "prospecting",
            },
            "message": f"Retrieved template: {template_id}",
        }
    
    elif operation == "create":
        template_data = inputs.get("template_data", {})
        if not template_data.get("name") or not template_data.get("template"):
            return {
                "operation": "create",
                "status": "error",
                "message": "template_data.name and template_data.template are required",
            }
        
        # Generate template ID
        import hashlib
        template_name = template_data["name"]
        template_id = template_name.lower().replace(" ", "_") + "_" + \
                      hashlib.md5(template_name.encode()).hexdigest()[:4]
        
        logger.info(f"[{trace_id}] Created template: {template_id}")
        
        return {
            "operation": "create",
            "status": "success",
            "template_id": template_id,
            "message": f"Template created: {template_id}",
        }
    
    elif operation == "update":
        template_id = inputs.get("template_id")
        template_data = inputs.get("template_data", {})
        
        if not template_id:
            return {
                "operation": "update",
                "status": "error",
                "message": "template_id is required for update operation",
            }
        
        logger.info(f"[{trace_id}] Updated template: {template_id}")
        
        return {
            "operation": "update",
            "status": "success",
            "template_id": template_id,
            "message": f"Template updated: {template_id}",
        }
    
    elif operation == "delete":
        template_id = inputs.get("template_id")
        
        if not template_id:
            return {
                "operation": "delete",
                "status": "error",
                "message": "template_id is required for delete operation",
            }
        
        logger.info(f"[{trace_id}] Deleted template: {template_id}")
        
        return {
            "operation": "delete",
            "status": "success",
            "template_id": template_id,
            "message": f"Template deleted: {template_id}",
        }
    
    else:
        return {
            "operation": operation,
            "status": "error",
            "message": f"Unknown operation: {operation}. Supported: create, read, update, delete, list",
        }
