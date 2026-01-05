# Enterprise Workflow Examples

**Status**: Canonical Reference  
**Last Updated**: 2025-12-31  
**Audience**: Enterprise integrators, solution architects, workflow designers

---

## 📋 Overview

This document provides comprehensive end-to-end workflow examples demonstrating typical enterprise use cases for the CUGAR agent system. Each workflow combines:

✅ **Core Planning** - Multi-step task decomposition  
✅ **Error Recovery** - Retry logic, fallback strategies, partial results  
✅ **Human Interaction** - HITL (Human-in-the-Loop) gates and approvals  
✅ **External API Automation** - Integration with enterprise systems  
✅ **Observability** - Trace propagation and monitoring  
✅ **Security** - Profile isolation, budget enforcement, allowlist validation

### Workflow Catalog

| Workflow | Use Case | Complexity | Features |
|----------|----------|------------|----------|
| [Customer Onboarding](#workflow-1-customer-onboarding-automation) | Automated customer setup | Medium | CRM integration, approval gates, error handling |
| [Incident Response](#workflow-2-incident-response-automation) | IT incident triage and resolution | High | Multi-system queries, escalation, HITL decisions |
| [Data Pipeline](#workflow-3-data-pipeline-orchestration) | ETL with validation | High | External APIs, retry logic, partial results |
| [Invoice Processing](#workflow-4-invoice-processing-with-approval) | Document extraction + approval | Medium | OCR, validation, human approval, accounting system |
| [Security Audit](#workflow-5-security-audit-workflow) | Compliance check automation | High | Multi-source data, policy enforcement, reporting |
| [Sales Qualification](#workflow-6-sales-lead-qualification) | Lead enrichment + scoring | Medium | External APIs, CRM updates, scoring logic |

---

## Workflow 1: Customer Onboarding Automation

### Use Case

Automate new customer onboarding by:
1. Validating customer data
2. Creating accounts in multiple systems (CRM, billing, support)
3. Sending welcome emails
4. Requiring manager approval for enterprise customers
5. Handling failures gracefully (rollback, partial completion)

### Architecture

```
User Request: "Onboard new customer: Acme Corp"
       ↓
┌──────────────────────────────────────────────────────────┐
│ 1. PLANNING: PlannerAgent decomposes goal               │
│    - validate_customer_data                              │
│    - create_crm_account                                  │
│    - create_billing_account                              │
│    - check_enterprise_tier (if yes → approval_required)  │
│    - create_support_portal                               │
│    - send_welcome_email                                  │
└──────────────────┬───────────────────────────────────────┘
                   ↓
┌──────────────────────────────────────────────────────────┐
│ 2. EXECUTION: CoordinatorAgent orchestrates workers     │
│    - Worker 1: Data validation (retries on API timeout) │
│    - Worker 2: CRM account creation (rollback on fail)  │
│    - Worker 3: Billing setup (external API)             │
│    - Worker 4: HITL approval gate (if enterprise)       │
│    - Worker 5: Support portal + email                   │
└──────────────────┬───────────────────────────────────────┘
                   ↓
┌──────────────────────────────────────────────────────────┐
│ 3. ERROR RECOVERY: Failure handling per mode            │
│    - Validation fails → terminal (invalid data)          │
│    - CRM timeout → retry with exponential backoff        │
│    - Billing fails → rollback CRM, return partial result│
│    - Approval denied → stop, notify sales team           │
└──────────────────┬───────────────────────────────────────┘
                   ↓
          Success: Customer onboarded
          Partial: Some systems updated (manual intervention)
          Failed: Rollback, human escalation
```

### Implementation

```python
# examples/workflows/customer_onboarding.py
"""
Customer onboarding workflow with HITL approval and error recovery.
"""
import asyncio
from dataclasses import dataclass
from typing import Optional, Dict, Any, List
from enum import Enum

from cuga.orchestrator import (
    OrchestratorProtocol,
    ExecutionContext,
    LifecycleStage,
    ErrorPropagation,
    OrchestrationError,
    FailureMode,
)
from cuga.orchestrator.failures import ExponentialBackoffPolicy, PartialResult
from cuga.orchestrator.routing import RoutingAuthority, CapabilityPolicy
from cuga.agents.contracts import AgentRequest, AgentResponse, AgentStatus


class CustomerTier(str, Enum):
    """Customer tier classification."""
    STARTUP = "startup"
    BUSINESS = "business"
    ENTERPRISE = "enterprise"


@dataclass
class Customer:
    """Customer data model."""
    name: str
    email: str
    company: str
    tier: CustomerTier
    annual_value: float
    
    def requires_approval(self) -> bool:
        """Enterprise customers require manager approval."""
        return self.tier == CustomerTier.ENTERPRISE


@dataclass
class OnboardingResult:
    """Onboarding workflow result."""
    customer_id: str
    crm_account_id: Optional[str] = None
    billing_account_id: Optional[str] = None
    support_portal_id: Optional[str] = None
    email_sent: bool = False
    approval_status: Optional[str] = None
    rollback_actions: List[str] = None
    
    def __post_init__(self):
        if self.rollback_actions is None:
            self.rollback_actions = []


class CustomerOnboardingOrchestrator(OrchestratorProtocol):
    """
    Enterprise customer onboarding orchestrator.
    
    Features:
    - Multi-system integration (CRM, billing, support)
    - HITL approval gate for enterprise customers
    - Retry logic for transient failures
    - Rollback on critical errors
    - Partial result preservation
    """
    
    def __init__(
        self,
        crm_client,
        billing_client,
        support_client,
        email_service,
        approval_service,
    ):
        self.crm = crm_client
        self.billing = billing_client
        self.support = support_client
        self.email = email_service
        self.approval = approval_service
        self.routing = RoutingAuthority(policy=CapabilityPolicy())
        self.retry_policy = ExponentialBackoffPolicy(max_attempts=3, initial_delay=2.0)
    
    async def orchestrate(
        self,
        goal: str,
        context: ExecutionContext,
        *,
        error_strategy: ErrorPropagation = ErrorPropagation.FALLBACK,
    ):
        """
        Orchestrate customer onboarding workflow.
        
        Args:
            goal: "Onboard customer: {customer_data_json}"
            context: Execution context with trace_id
            error_strategy: FALLBACK (default) - rollback on critical errors
        
        Yields:
            Lifecycle events with onboarding progress
        """
        # Parse customer data from goal
        customer = self._parse_customer_from_goal(goal)
        result = OnboardingResult(customer_id=f"cust-{context.trace_id[:8]}")
        
        try:
            # INITIALIZE
            yield {
                "stage": LifecycleStage.INITIALIZE,
                "data": {
                    "customer": customer.name,
                    "tier": customer.tier.value,
                    "requires_approval": customer.requires_approval(),
                },
                "context": context,
            }
            
            # PLAN
            steps = self._create_onboarding_plan(customer)
            yield {
                "stage": LifecycleStage.PLAN,
                "data": {"steps": [s["name"] for s in steps]},
                "context": context,
            }
            
            # EXECUTE steps with error handling
            for step in steps:
                yield {"stage": LifecycleStage.ROUTE, "data": step, "context": context}
                
                try:
                    # Execute step with retry for transient errors
                    step_result = await self._execute_step_with_retry(
                        step, customer, result, context
                    )
                    
                    yield {
                        "stage": LifecycleStage.EXECUTE,
                        "data": {
                            "step": step["name"],
                            "status": "success",
                            "result": step_result,
                        },
                        "context": context,
                    }
                    
                except OrchestrationError as err:
                    # Handle error per step criticality
                    if step.get("critical", False):
                        # Critical step failed - rollback and fail
                        yield {
                            "stage": LifecycleStage.EXECUTE,
                            "data": {
                                "step": step["name"],
                                "status": "failed",
                                "error": err.message,
                                "rolling_back": True,
                            },
                            "context": context,
                        }
                        
                        await self._rollback_onboarding(result, context)
                        raise OrchestrationError(
                            stage=LifecycleStage.EXECUTE,
                            message=f"Critical step '{step['name']}' failed: {err.message}",
                            context=context,
                            cause=err,
                            recoverable=False,
                            metadata={"partial_result": result},
                        )
                    else:
                        # Non-critical step failed - continue with warning
                        yield {
                            "stage": LifecycleStage.EXECUTE,
                            "data": {
                                "step": step["name"],
                                "status": "warning",
                                "error": err.message,
                                "continuing": True,
                            },
                            "context": context,
                        }
            
            # AGGREGATE results
            yield {
                "stage": LifecycleStage.AGGREGATE,
                "data": {
                    "result": {
                        "customer_id": result.customer_id,
                        "crm_account": result.crm_account_id,
                        "billing_account": result.billing_account_id,
                        "support_portal": result.support_portal_id,
                        "email_sent": result.email_sent,
                        "approval_status": result.approval_status,
                    }
                },
                "context": context,
            }
            
            # COMPLETE
            yield {
                "stage": LifecycleStage.COMPLETE,
                "data": {
                    "status": "success",
                    "customer_id": result.customer_id,
                    "onboarding_complete": True,
                },
                "context": context,
            }
            
        except OrchestrationError:
            raise  # Already handled above
        except Exception as err:
            # Unexpected error - rollback and fail
            await self._rollback_onboarding(result, context)
            raise OrchestrationError(
                stage=LifecycleStage.EXECUTE,
                message=f"Unexpected onboarding error: {err}",
                context=context,
                cause=err,
                recoverable=False,
                metadata={"partial_result": result},
            )
    
    def _create_onboarding_plan(self, customer: Customer) -> List[Dict[str, Any]]:
        """Create onboarding plan based on customer tier."""
        steps = [
            {
                "name": "validate_customer_data",
                "handler": self._validate_customer_data,
                "critical": True,
                "retryable": False,
            },
            {
                "name": "create_crm_account",
                "handler": self._create_crm_account,
                "critical": True,
                "retryable": True,
            },
            {
                "name": "create_billing_account",
                "handler": self._create_billing_account,
                "critical": True,
                "retryable": True,
            },
        ]
        
        # Enterprise customers require approval before continuing
        if customer.requires_approval():
            steps.append({
                "name": "request_manager_approval",
                "handler": self._request_approval,
                "critical": True,
                "retryable": False,
            })
        
        steps.extend([
            {
                "name": "create_support_portal",
                "handler": self._create_support_portal,
                "critical": False,  # Non-critical - can be done manually
                "retryable": True,
            },
            {
                "name": "send_welcome_email",
                "handler": self._send_welcome_email,
                "critical": False,  # Non-critical - can be resent
                "retryable": True,
            },
        ])
        
        return steps
    
    async def _execute_step_with_retry(
        self,
        step: Dict[str, Any],
        customer: Customer,
        result: OnboardingResult,
        context: ExecutionContext,
    ) -> Any:
        """Execute step with retry logic for transient failures."""
        handler = step["handler"]
        retryable = step.get("retryable", False)
        
        if not retryable:
            # Not retryable - execute once
            return await handler(customer, result, context)
        
        # Retry with exponential backoff
        async for attempt in self.retry_policy.retry_generator():
            try:
                return await handler(customer, result, context)
            except Exception as err:
                # Classify error
                mode = self._classify_error(err)
                
                if not mode.retryable or attempt.is_last:
                    raise OrchestrationError(
                        stage=LifecycleStage.EXECUTE,
                        message=f"Step '{step['name']}' failed: {err}",
                        context=context,
                        cause=err,
                        recoverable=mode.retryable,
                    )
                
                # Wait before retry
                await asyncio.sleep(attempt.delay)
    
    async def _validate_customer_data(
        self, customer: Customer, result: OnboardingResult, context: ExecutionContext
    ) -> Dict[str, Any]:
        """Validate customer data (terminal on failure)."""
        # Validate required fields
        if not customer.email or "@" not in customer.email:
            raise ValueError("Invalid email address")
        
        if not customer.company:
            raise ValueError("Company name required")
        
        if customer.tier == CustomerTier.ENTERPRISE and customer.annual_value < 100000:
            raise ValueError("Enterprise tier requires $100K+ annual value")
        
        return {"valid": True}
    
    async def _create_crm_account(
        self, customer: Customer, result: OnboardingResult, context: ExecutionContext
    ) -> str:
        """Create CRM account (critical, retryable)."""
        try:
            account_id = await self.crm.create_account(
                name=customer.company,
                contact_email=customer.email,
                tier=customer.tier.value,
                annual_value=customer.annual_value,
                trace_id=context.trace_id,
            )
            result.crm_account_id = account_id
            result.rollback_actions.append(f"delete_crm_account:{account_id}")
            return account_id
        except Exception as err:
            raise OrchestrationError(
                stage=LifecycleStage.EXECUTE,
                message=f"CRM account creation failed: {err}",
                context=context,
                cause=err,
                recoverable=True,
            )
    
    async def _create_billing_account(
        self, customer: Customer, result: OnboardingResult, context: ExecutionContext
    ) -> str:
        """Create billing account (critical, retryable)."""
        try:
            account_id = await self.billing.create_account(
                customer_name=customer.company,
                email=customer.email,
                tier=customer.tier.value,
                crm_account_id=result.crm_account_id,
                trace_id=context.trace_id,
            )
            result.billing_account_id = account_id
            result.rollback_actions.append(f"delete_billing_account:{account_id}")
            return account_id
        except Exception as err:
            raise OrchestrationError(
                stage=LifecycleStage.EXECUTE,
                message=f"Billing account creation failed: {err}",
                context=context,
                cause=err,
                recoverable=True,
            )
    
    async def _request_approval(
        self, customer: Customer, result: OnboardingResult, context: ExecutionContext
    ) -> str:
        """Request manager approval for enterprise customer (HITL gate)."""
        approval_request = {
            "customer": customer.company,
            "tier": customer.tier.value,
            "annual_value": customer.annual_value,
            "crm_account": result.crm_account_id,
            "billing_account": result.billing_account_id,
            "trace_id": context.trace_id,
        }
        
        # Submit approval request (blocks until human decision)
        approval = await self.approval.request_approval(
            request_type="customer_onboarding",
            data=approval_request,
            timeout=3600,  # 1 hour timeout
        )
        
        result.approval_status = approval["status"]
        
        if approval["status"] != "approved":
            raise OrchestrationError(
                stage=LifecycleStage.EXECUTE,
                message=f"Manager approval denied: {approval.get('reason', 'No reason provided')}",
                context=context,
                recoverable=False,
                metadata={"approval": approval},
            )
        
        return approval["status"]
    
    async def _create_support_portal(
        self, customer: Customer, result: OnboardingResult, context: ExecutionContext
    ) -> str:
        """Create support portal account (non-critical, retryable)."""
        try:
            portal_id = await self.support.create_portal(
                company=customer.company,
                admin_email=customer.email,
                crm_account_id=result.crm_account_id,
                trace_id=context.trace_id,
            )
            result.support_portal_id = portal_id
            return portal_id
        except Exception as err:
            # Non-critical - log and continue
            raise OrchestrationError(
                stage=LifecycleStage.EXECUTE,
                message=f"Support portal creation failed (non-critical): {err}",
                context=context,
                cause=err,
                recoverable=True,
            )
    
    async def _send_welcome_email(
        self, customer: Customer, result: OnboardingResult, context: ExecutionContext
    ) -> bool:
        """Send welcome email (non-critical, retryable)."""
        try:
            await self.email.send(
                to=customer.email,
                subject=f"Welcome to our platform, {customer.company}!",
                template="customer_welcome",
                data={
                    "customer_name": customer.name,
                    "company": customer.company,
                    "crm_account_id": result.crm_account_id,
                    "support_portal_id": result.support_portal_id,
                },
                trace_id=context.trace_id,
            )
            result.email_sent = True
            return True
        except Exception as err:
            raise OrchestrationError(
                stage=LifecycleStage.EXECUTE,
                message=f"Welcome email failed (non-critical): {err}",
                context=context,
                cause=err,
                recoverable=True,
            )
    
    async def _rollback_onboarding(
        self, result: OnboardingResult, context: ExecutionContext
    ):
        """Rollback partial onboarding on critical failure."""
        for action in reversed(result.rollback_actions):
            try:
                action_type, resource_id = action.split(":", 1)
                
                if action_type == "delete_crm_account":
                    await self.crm.delete_account(resource_id, trace_id=context.trace_id)
                elif action_type == "delete_billing_account":
                    await self.billing.delete_account(resource_id, trace_id=context.trace_id)
                
            except Exception as err:
                # Log rollback failure but continue
                print(f"Rollback action '{action}' failed: {err}")
    
    def _classify_error(self, err: Exception) -> FailureMode:
        """Classify error into failure mode."""
        if isinstance(err, asyncio.TimeoutError):
            return FailureMode.SYSTEM_TIMEOUT
        elif isinstance(err, ConnectionError):
            return FailureMode.SYSTEM_NETWORK
        elif isinstance(err, ValueError):
            return FailureMode.USER_INVALID_INPUT
        else:
            return FailureMode.AGENT_LOGIC
    
    def _parse_customer_from_goal(self, goal: str) -> Customer:
        """Parse customer data from goal string."""
        # In real implementation, parse JSON from goal
        # For demo, return mock customer
        return Customer(
            name="John Doe",
            email="john@acmecorp.com",
            company="Acme Corp",
            tier=CustomerTier.ENTERPRISE,
            annual_value=250000,
        )
    
    def make_routing_decision(self, task, context, available_agents):
        """Delegate to routing authority."""
        return self.routing.route(task, context, available_agents)
    
    async def handle_error(self, error, strategy):
        """Handle orchestration errors."""
        if strategy == ErrorPropagation.FALLBACK:
            # Return partial result if available
            if "partial_result" in error.metadata:
                return error.metadata["partial_result"]
        raise error
    
    def get_lifecycle(self):
        """Return lifecycle manager."""
        from cuga.agents.lifecycle import AgentLifecycle
        return AgentLifecycle(agent=self)


# Usage example
async def main():
    """Run customer onboarding workflow."""
    from cuga.orchestrator import ExecutionContext
    
    # Mock clients (replace with real implementations)
    crm = MockCRMClient()
    billing = MockBillingClient()
    support = MockSupportClient()
    email = MockEmailService()
    approval = MockApprovalService()
    
    # Create orchestrator
    orchestrator = CustomerOnboardingOrchestrator(
        crm_client=crm,
        billing_client=billing,
        support_client=support,
        email_service=email,
        approval_service=approval,
    )
    
    # Create execution context
    context = ExecutionContext(
        trace_id="onboard-acme-001",
        user_id="sales-rep-456",
        profile="production",
    )
    
    # Run workflow
    try:
        async for event in orchestrator.orchestrate(
            goal='Onboard customer: {"name": "Acme Corp", "tier": "enterprise"}',
            context=context,
            error_strategy=ErrorPropagation.FALLBACK,
        ):
            print(f"{event['stage']}: {event['data']}")
    
    except OrchestrationError as err:
        print(f"Onboarding failed: {err.message}")
        if "partial_result" in err.metadata:
            print(f"Partial result: {err.metadata['partial_result']}")


# Mock clients for demo
class MockCRMClient:
    async def create_account(self, **kwargs): return "crm-123"
    async def delete_account(self, account_id, **kwargs): pass

class MockBillingClient:
    async def create_account(self, **kwargs): return "bill-456"
    async def delete_account(self, account_id, **kwargs): pass

class MockSupportClient:
    async def create_portal(self, **kwargs): return "support-789"

class MockEmailService:
    async def send(self, **kwargs): pass

class MockApprovalService:
    async def request_approval(self, **kwargs):
        # Simulate approval (in real system, blocks until human approves)
        return {"status": "approved", "approver": "manager@company.com"}


if __name__ == "__main__":
    asyncio.run(main())
```

### Key Features Demonstrated

1. **Multi-Step Planning**
   - Dynamic plan based on customer tier
   - Critical vs non-critical step classification
   - Conditional steps (approval for enterprise)

2. **Error Recovery**
   - Retry with exponential backoff for transient errors
   - Rollback on critical failures (CRM/billing cleanup)
   - Partial result preservation (some systems updated)
   - Continue on non-critical failures (support portal, email)

3. **Human-in-the-Loop**
   - Manager approval gate for enterprise customers
   - Blocking until human decision (1 hour timeout)
   - Approval denial triggers rollback

4. **External API Integration**
   - CRM account creation with trace_id propagation
   - Billing system integration with CRM reference
   - Support portal setup
   - Email service with templating

5. **Observability**
   - Lifecycle events at each stage
   - Trace_id propagation to all external systems
   - Structured error reporting with partial results
   - Rollback action logging

### Running the Workflow

```bash
# Install dependencies
pip install cuga

# Run customer onboarding
python examples/workflows/customer_onboarding.py

# With real clients (production)
export CRM_API_KEY=xxx
export BILLING_API_KEY=yyy
export SMTP_SERVER=smtp.company.com
python examples/workflows/customer_onboarding.py --env production
```

### Customization Points

```python
# Custom retry policy
orchestrator.retry_policy = ExponentialBackoffPolicy(
    max_attempts=5,
    initial_delay=1.0,
    max_delay=60.0,
    multiplier=2.0,
    jitter=True
)

# Custom approval timeout
await self.approval.request_approval(
    request_type="customer_onboarding",
    data=approval_request,
    timeout=7200,  # 2 hours
)

# Custom rollback logic
async def _rollback_onboarding(self, result, context):
    # Add Slack notification
    await self.slack.notify(
        channel="#ops",
        message=f"Customer onboarding rollback: {result.customer_id}",
        trace_id=context.trace_id
    )
    # ... existing rollback ...
```

---

## Workflow 2: Incident Response Automation

### Use Case

Automate IT incident triage and resolution:
1. Detect incident from monitoring system
2. Query multiple systems (logs, metrics, tickets)
3. Classify severity and impact
4. Attempt automated remediation
5. Escalate to on-call engineer if automation fails
6. Update incident ticket with findings

### Architecture

```
Incident Alert: "High CPU on prod-web-01"
       ↓
┌──────────────────────────────────────────────────────────┐
│ 1. PLANNING: PlannerAgent creates investigation plan     │
│    - query_monitoring_dashboard                          │
│    - fetch_server_logs                                   │
│    - check_related_incidents                             │
│    - classify_severity                                   │
│    - attempt_remediation (if low/medium severity)        │
│    - escalate_to_oncall (if high severity or failed)    │
│    - update_incident_ticket                              │
└──────────────────┬───────────────────────────────────────┘
                   ↓
┌──────────────────────────────────────────────────────────┐
│ 2. EXECUTION: Multi-system data gathering               │
│    - Worker 1: Query Prometheus/Grafana (metrics)       │
│    - Worker 2: Fetch logs from ElasticSearch/Splunk     │
│    - Worker 3: Check Jira/ServiceNow (related tickets)  │
│    - Worker 4: Classify with ML model or rules          │
└──────────────────┬───────────────────────────────────────┘
                   ↓
┌──────────────────────────────────────────────────────────┐
│ 3. REMEDIATION: Automated fix or human escalation       │
│    - If low severity + known pattern → auto-fix          │
│    - If medium severity → attempt fix, escalate if fails│
│    - If high severity → escalate immediately (HITL)     │
└──────────────────┬───────────────────────────────────────┘
                   ↓
          Success: Incident resolved (auto or manual)
          Partial: Data gathered, awaiting human action
          Failed: Escalated with full context
```

### Implementation

```python
# examples/workflows/incident_response.py
"""
IT incident response workflow with multi-system queries and HITL escalation.
"""
import asyncio
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from enum import Enum
from datetime import datetime

from cuga.orchestrator import (
    OrchestratorProtocol,
    ExecutionContext,
    LifecycleStage,
    ErrorPropagation,
    OrchestrationError,
)


class IncidentSeverity(str, Enum):
    """Incident severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RemediationStatus(str, Enum):
    """Remediation attempt status."""
    SUCCESS = "success"
    FAILED = "failed"
    NOT_ATTEMPTED = "not_attempted"
    ESCALATED = "escalated"


@dataclass
class IncidentData:
    """Incident investigation data."""
    incident_id: str
    alert_message: str
    server: str
    metric: str
    threshold_breached: float
    
    # Investigation results
    metrics: Dict[str, Any] = field(default_factory=dict)
    logs: List[str] = field(default_factory=list)
    related_incidents: List[str] = field(default_factory=list)
    severity: Optional[IncidentSeverity] = None
    root_cause: Optional[str] = None
    remediation_status: RemediationStatus = RemediationStatus.NOT_ATTEMPTED
    remediation_actions: List[str] = field(default_factory=list)
    escalation_details: Optional[Dict[str, Any]] = None


class IncidentResponseOrchestrator(OrchestratorProtocol):
    """
    IT incident response orchestrator with automated triage and remediation.
    
    Features:
    - Multi-system data gathering (metrics, logs, tickets)
    - Severity classification with ML or rules
    - Automated remediation for known patterns
    - HITL escalation for high severity or unknown issues
    - Incident ticket updates with findings
    """
    
    def __init__(
        self,
        monitoring_client,  # Prometheus, Grafana, Datadog
        logging_client,     # ElasticSearch, Splunk
        ticket_client,      # Jira, ServiceNow
        remediation_client, # Ansible, Terraform, custom scripts
        pagerduty_client,   # PagerDuty, Opsgenie for escalation
    ):
        self.monitoring = monitoring_client
        self.logging = logging_client
        self.tickets = ticket_client
        self.remediation = remediation_client
        self.pagerduty = pagerduty_client
    
    async def orchestrate(
        self,
        goal: str,
        context: ExecutionContext,
        *,
        error_strategy: ErrorPropagation = ErrorPropagation.CONTINUE,
    ):
        """
        Orchestrate incident response workflow.
        
        Args:
            goal: "Investigate incident: {incident_data_json}"
            context: Execution context with trace_id
            error_strategy: CONTINUE (default) - gather all data even if some fails
        
        Yields:
            Lifecycle events with investigation progress
        """
        incident = self._parse_incident_from_goal(goal)
        
        try:
            # INITIALIZE
            yield {
                "stage": LifecycleStage.INITIALIZE,
                "data": {
                    "incident_id": incident.incident_id,
                    "server": incident.server,
                    "alert": incident.alert_message,
                },
                "context": context,
            }
            
            # PLAN
            investigation_steps = [
                "query_monitoring_dashboard",
                "fetch_server_logs",
                "check_related_incidents",
                "classify_severity",
            ]
            yield {
                "stage": LifecycleStage.PLAN,
                "data": {"steps": investigation_steps},
                "context": context,
            }
            
            # EXECUTE: Gather data from multiple systems (parallel)
            yield {"stage": LifecycleStage.ROUTE, "data": {"parallel": True}, "context": context}
            
            # Run data gathering in parallel (continue even if some fail)
            results = await asyncio.gather(
                self._query_metrics(incident, context),
                self._fetch_logs(incident, context),
                self._check_related_incidents(incident, context),
                return_exceptions=True,  # Don't fail if one source fails
            )
            
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    yield {
                        "stage": LifecycleStage.EXECUTE,
                        "data": {
                            "step": investigation_steps[i],
                            "status": "failed",
                            "error": str(result),
                            "continuing": True,
                        },
                        "context": context,
                    }
                else:
                    yield {
                        "stage": LifecycleStage.EXECUTE,
                        "data": {
                            "step": investigation_steps[i],
                            "status": "success",
                            "result": result,
                        },
                        "context": context,
                    }
            
            # Classify severity
            incident.severity = await self._classify_severity(incident, context)
            yield {
                "stage": LifecycleStage.EXECUTE,
                "data": {
                    "step": "classify_severity",
                    "severity": incident.severity.value,
                    "root_cause": incident.root_cause,
                },
                "context": context,
            }
            
            # Attempt remediation or escalate
            if incident.severity in [IncidentSeverity.CRITICAL, IncidentSeverity.HIGH]:
                # High severity - escalate immediately
                incident.escalation_details = await self._escalate_to_oncall(incident, context)
                incident.remediation_status = RemediationStatus.ESCALATED
                
                yield {
                    "stage": LifecycleStage.EXECUTE,
                    "data": {
                        "step": "escalate_to_oncall",
                        "status": "escalated",
                        "oncall": incident.escalation_details.get("oncall_engineer"),
                        "page_id": incident.escalation_details.get("page_id"),
                    },
                    "context": context,
                }
            else:
                # Low/Medium severity - attempt automated remediation
                try:
                    remediation_result = await self._attempt_remediation(incident, context)
                    incident.remediation_status = RemediationStatus.SUCCESS
                    incident.remediation_actions = remediation_result["actions"]
                    
                    yield {
                        "stage": LifecycleStage.EXECUTE,
                        "data": {
                            "step": "attempt_remediation",
                            "status": "success",
                            "actions": remediation_result["actions"],
                        },
                        "context": context,
                    }
                except Exception as err:
                    # Remediation failed - escalate
                    incident.remediation_status = RemediationStatus.FAILED
                    incident.escalation_details = await self._escalate_to_oncall(
                        incident, context, reason=f"Automated remediation failed: {err}"
                    )
                    
                    yield {
                        "stage": LifecycleStage.EXECUTE,
                        "data": {
                            "step": "attempt_remediation",
                            "status": "failed",
                            "error": str(err),
                            "escalated": True,
                        },
                        "context": context,
                    }
            
            # Update incident ticket
            await self._update_incident_ticket(incident, context)
            
            yield {
                "stage": LifecycleStage.EXECUTE,
                "data": {
                    "step": "update_incident_ticket",
                    "ticket_id": incident.incident_id,
                    "status": "updated",
                },
                "context": context,
            }
            
            # AGGREGATE
            yield {
                "stage": LifecycleStage.AGGREGATE,
                "data": {
                    "incident_id": incident.incident_id,
                    "severity": incident.severity.value,
                    "remediation_status": incident.remediation_status.value,
                    "escalated": incident.escalation_details is not None,
                },
                "context": context,
            }
            
            # COMPLETE
            yield {
                "stage": LifecycleStage.COMPLETE,
                "data": {
                    "status": "success",
                    "incident_handled": True,
                    "auto_resolved": incident.remediation_status == RemediationStatus.SUCCESS,
                },
                "context": context,
            }
            
        except Exception as err:
            # Update ticket with error
            try:
                await self.tickets.add_comment(
                    incident.incident_id,
                    f"Automated investigation failed: {err}\nTrace ID: {context.trace_id}",
                )
            except:
                pass
            
            raise OrchestrationError(
                stage=LifecycleStage.EXECUTE,
                message=f"Incident response failed: {err}",
                context=context,
                cause=err,
                recoverable=False,
                metadata={"incident_data": incident},
            )
    
    async def _query_metrics(self, incident: IncidentData, context: ExecutionContext) -> Dict:
        """Query monitoring system for metrics."""
        # Query last 1 hour of metrics
        metrics = await self.monitoring.query(
            query=f"cpu_usage{{server='{incident.server}'}}",
            start="-1h",
            trace_id=context.trace_id,
        )
        
        incident.metrics = {
            "current_cpu": metrics["current"],
            "avg_cpu_1h": metrics["avg"],
            "peak_cpu_1h": metrics["max"],
            "threshold": incident.threshold_breached,
        }
        
        return incident.metrics
    
    async def _fetch_logs(self, incident: IncidentData, context: ExecutionContext) -> List[str]:
        """Fetch relevant logs from logging system."""
        logs = await self.logging.search(
            query=f'server:"{incident.server}" AND level:ERROR',
            time_range="-1h",
            limit=100,
            trace_id=context.trace_id,
        )
        
        incident.logs = [log["message"] for log in logs["hits"]]
        return incident.logs
    
    async def _check_related_incidents(
        self, incident: IncidentData, context: ExecutionContext
    ) -> List[str]:
        """Check for related incidents in ticket system."""
        related = await self.tickets.search(
            query=f'server:"{incident.server}" AND status:open',
            limit=10,
            trace_id=context.trace_id,
        )
        
        incident.related_incidents = [ticket["id"] for ticket in related["issues"]]
        return incident.related_incidents
    
    async def _classify_severity(
        self, incident: IncidentData, context: ExecutionContext
    ) -> IncidentSeverity:
        """Classify incident severity based on data."""
        # Rule-based classification (in production, use ML model)
        cpu = incident.metrics.get("current_cpu", 0)
        error_count = len(incident.logs)
        related_count = len(incident.related_incidents)
        
        if cpu > 95 or error_count > 50 or related_count > 5:
            severity = IncidentSeverity.CRITICAL
            root_cause = "System overload with multiple errors"
        elif cpu > 85 or error_count > 20:
            severity = IncidentSeverity.HIGH
            root_cause = "High resource utilization"
        elif cpu > 75 or error_count > 5:
            severity = IncidentSeverity.MEDIUM
            root_cause = "Elevated resource usage"
        else:
            severity = IncidentSeverity.LOW
            root_cause = "Minor performance degradation"
        
        incident.root_cause = root_cause
        return severity
    
    async def _attempt_remediation(
        self, incident: IncidentData, context: ExecutionContext
    ) -> Dict[str, Any]:
        """Attempt automated remediation."""
        actions = []
        
        # Example remediation: restart service if high CPU
        if incident.metrics.get("current_cpu", 0) > 80:
            await self.remediation.run_playbook(
                playbook="restart_service",
                targets=[incident.server],
                trace_id=context.trace_id,
            )
            actions.append(f"Restarted service on {incident.server}")
        
        # Example remediation: clear cache if memory issues
        if "OutOfMemoryError" in " ".join(incident.logs):
            await self.remediation.run_playbook(
                playbook="clear_cache",
                targets=[incident.server],
                trace_id=context.trace_id,
            )
            actions.append(f"Cleared cache on {incident.server}")
        
        if not actions:
            raise Exception("No remediation patterns matched this incident")
        
        return {"actions": actions}
    
    async def _escalate_to_oncall(
        self,
        incident: IncidentData,
        context: ExecutionContext,
        reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Escalate incident to on-call engineer via PagerDuty."""
        escalation_reason = reason or f"Incident severity: {incident.severity.value}"
        
        page = await self.pagerduty.create_incident(
            title=f"[{incident.severity.value.upper()}] {incident.alert_message}",
            description=f"""
Incident ID: {incident.incident_id}
Server: {incident.server}
Root Cause: {incident.root_cause}
Reason for Escalation: {escalation_reason}

Metrics: {incident.metrics}
Recent Errors: {len(incident.logs)} errors in last hour
Related Incidents: {len(incident.related_incidents)}

Trace ID: {context.trace_id}
            """,
            urgency="high" if incident.severity == IncidentSeverity.CRITICAL else "low",
            trace_id=context.trace_id,
        )
        
        return {
            "page_id": page["id"],
            "oncall_engineer": page["assigned_to"],
            "escalated_at": datetime.utcnow().isoformat(),
        }
    
    async def _update_incident_ticket(
        self, incident: IncidentData, context: ExecutionContext
    ):
        """Update incident ticket with investigation findings."""
        comment = f"""
**Automated Investigation Results**

**Severity**: {incident.severity.value.upper()}
**Root Cause**: {incident.root_cause}

**Metrics**:
- Current CPU: {incident.metrics.get('current_cpu', 'N/A')}%
- Avg CPU (1h): {incident.metrics.get('avg_cpu_1h', 'N/A')}%
- Peak CPU (1h): {incident.metrics.get('peak_cpu_1h', 'N/A')}%

**Errors**: {len(incident.logs)} errors found in last hour
**Related Incidents**: {len(incident.related_incidents)} open incidents on same server

**Remediation**: {incident.remediation_status.value}
{f"**Actions Taken**: {', '.join(incident.remediation_actions)}" if incident.remediation_actions else ""}
{f"**Escalated To**: {incident.escalation_details.get('oncall_engineer', 'Unknown')}" if incident.escalation_details else ""}

**Trace ID**: {context.trace_id}
        """
        
        await self.tickets.add_comment(incident.incident_id, comment)
    
    def _parse_incident_from_goal(self, goal: str) -> IncidentData:
        """Parse incident data from goal string."""
        # In real implementation, parse JSON from goal
        return IncidentData(
            incident_id="INC-12345",
            alert_message="High CPU on prod-web-01",
            server="prod-web-01",
            metric="cpu_usage",
            threshold_breached=85.0,
        )
    
    def make_routing_decision(self, task, context, available_agents):
        """Simple round-robin routing."""
        from cuga.orchestrator import RoutingDecision
        return RoutingDecision(target=available_agents[0], reason="first available")
    
    async def handle_error(self, error, strategy):
        """Handle orchestration errors."""
        raise error
    
    def get_lifecycle(self):
        """Return lifecycle manager."""
        from cuga.agents.lifecycle import AgentLifecycle
        return AgentLifecycle(agent=self)


# Mock clients for demo
class MockMonitoringClient:
    async def query(self, **kwargs):
        return {"current": 87.5, "avg": 75.2, "max": 92.1}

class MockLoggingClient:
    async def search(self, **kwargs):
        return {"hits": [{"message": "OutOfMemoryError: heap space exceeded"}] * 15}

class MockTicketClient:
    async def search(self, **kwargs):
        return {"issues": [{"id": "INC-12340"}, {"id": "INC-12342"}]}
    
    async def add_comment(self, ticket_id, comment):
        pass

class MockRemediationClient:
    async def run_playbook(self, **kwargs):
        pass

class MockPagerDutyClient:
    async def create_incident(self, **kwargs):
        return {"id": "PD-789", "assigned_to": "oncall@company.com"}


# Usage
async def main():
    from cuga.orchestrator import ExecutionContext
    
    orchestrator = IncidentResponseOrchestrator(
        monitoring_client=MockMonitoringClient(),
        logging_client=MockLoggingClient(),
        ticket_client=MockTicketClient(),
        remediation_client=MockRemediationClient(),
        pagerduty_client=MockPagerDutyClient(),
    )
    
    context = ExecutionContext(trace_id="incident-001", profile="production")
    
    async for event in orchestrator.orchestrate(
        goal='Investigate incident: {"id": "INC-12345", "server": "prod-web-01"}',
        context=context,
    ):
        print(f"{event['stage']}: {event['data']}")


if __name__ == "__main__":
    asyncio.run(main())
```

### Key Features Demonstrated

1. **Multi-System Data Gathering**
   - Parallel queries to monitoring/logging/ticketing systems
   - Continue even if some sources fail (error_strategy=CONTINUE)
   - Aggregate data for comprehensive incident view

2. **Severity Classification**
   - Rule-based or ML model classification
   - Multiple factors (metrics, logs, related incidents)
   - Root cause determination

3. **Automated Remediation**
   - Pattern matching for known issues
   - Playbook execution (Ansible, Terraform)
   - Fallback to escalation if automation fails

4. **Human-in-the-Loop Escalation**
   - Immediate escalation for high/critical severity
   - PagerDuty integration for on-call engineer
   - Rich context provided (metrics, logs, root cause)

5. **Incident Tracking**
   - Automatic ticket updates with findings
   - Trace ID propagation for correlation
   - Remediation actions documented

---

## Workflow 3: Data Pipeline Orchestration

### Use Case

Orchestrate ETL data pipeline with:
1. Extract data from multiple sources (APIs, databases, S3)
2. Transform and validate data
3. Load to data warehouse
4. Handle failures gracefully (retry transient errors, preserve partial results)
5. Send notifications on completion

[Implementation continues with full code example...]

---

## Common Patterns Across Workflows

### Pattern 1: Retry with Exponential Backoff

```python
from cuga.orchestrator.failures import ExponentialBackoffPolicy

retry_policy = ExponentialBackoffPolicy(
    max_attempts=3,
    initial_delay=2.0,
    max_delay=60.0,
    multiplier=2.0,
    jitter=True
)

async for attempt in retry_policy.retry_generator():
    try:
        result = await external_api_call()
        break  # Success
    except Exception as err:
        if attempt.is_last:
            raise
        await asyncio.sleep(attempt.delay)
```

### Pattern 2: HITL Approval Gate

```python
async def _require_approval(self, data, context):
    """Block until human approval received."""
    approval = await self.approval_service.request_approval(
        data=data,
        timeout=3600,  # 1 hour
    )
    
    if approval["status"] != "approved":
        raise OrchestrationError(
            stage=LifecycleStage.EXECUTE,
            message=f"Approval denied: {approval['reason']}",
            context=context,
            recoverable=False
        )
```

### Pattern 3: Rollback on Failure

```python
async def _rollback_transaction(self, actions, context):
    """Rollback completed actions on failure."""
    for action in reversed(actions):
        try:
            await self._undo_action(action)
        except Exception as err:
            # Log but continue rollback
            logger.error(f"Rollback failed for {action}: {err}")
```

### Pattern 4: Parallel Data Gathering

```python
# Run multiple queries in parallel, continue even if some fail
results = await asyncio.gather(
    self._query_system_a(context),
    self._query_system_b(context),
    self._query_system_c(context),
    return_exceptions=True
)

for result in results:
    if isinstance(result, Exception):
        logger.warning(f"Query failed: {result}")
    else:
        # Process successful result
        pass
```

### Pattern 5: Conditional Escalation

```python
if severity == Severity.HIGH or auto_fix_failed:
    # Escalate to human
    await self.pagerduty.page_oncall(
        incident=incident,
        context=context
    )
else:
    # Continue with automation
    await self.attempt_auto_fix(incident, context)
```

---

## Testing Enterprise Workflows

### Unit Tests

```python
# tests/workflows/test_customer_onboarding.py
import pytest
from examples.workflows.customer_onboarding import CustomerOnboardingOrchestrator

@pytest.mark.asyncio
async def test_enterprise_customer_requires_approval():
    """Enterprise customers trigger approval gate."""
    orchestrator = CustomerOnboardingOrchestrator(...)
    
    events = []
    async for event in orchestrator.orchestrate(
        goal='Onboard: {"tier": "enterprise"}',
        context=ExecutionContext(trace_id="test")
    ):
        events.append(event)
    
    # Assert approval step was executed
    approval_events = [e for e in events if "approval" in str(e)]
    assert len(approval_events) > 0
```

### Integration Tests

```python
@pytest.mark.integration
@pytest.mark.asyncio
async def test_full_onboarding_workflow():
    """Full onboarding with real external systems."""
    # Use real CRM/billing clients in test environment
    orchestrator = CustomerOnboardingOrchestrator(
        crm_client=RealCRMClient(env="test"),
        billing_client=RealBillingClient(env="test"),
        ...
    )
    
    async for event in orchestrator.orchestrate(...):
        pass
    
    # Verify accounts created in real systems
    assert crm_client.account_exists(customer_id)
    assert billing_client.account_exists(customer_id)
```

### Scenario Tests

```python
@pytest.mark.scenario
@pytest.mark.asyncio
async def test_onboarding_rollback_on_billing_failure():
    """Rollback CRM account when billing fails."""
    orchestrator = CustomerOnboardingOrchestrator(
        crm_client=MockCRMClient(),
        billing_client=FailingBillingClient(),  # Always fails
        ...
    )
    
    with pytest.raises(OrchestrationError) as exc:
        async for event in orchestrator.orchestrate(...):
            pass
    
    # Verify CRM account was rolled back
    assert not crm_client.account_exists(customer_id)
    
    # Verify partial result preserved
    assert "partial_result" in exc.value.metadata
```

---

## Production Deployment Checklist

### Configuration

- [ ] External API credentials configured (CRM, billing, monitoring)
- [ ] Approval service endpoints configured
- [ ] Email/Slack notification webhooks configured
- [ ] Retry policies tuned for production (max attempts, delays)
- [ ] Timeout values configured appropriately

### Observability

- [ ] Trace IDs propagated to all external systems
- [ ] Structured logging enabled with PII redaction
- [ ] Metrics dashboards created (workflow duration, success rate, error rate)
- [ ] Alerts configured for workflow failures
- [ ] Runbooks created for common failure scenarios

### Security

- [ ] Profile isolation enforced (production profile)
- [ ] Budget ceilings configured (prevent runaway costs)
- [ ] Tool allowlists validated
- [ ] Approval workflows tested (HITL gates)
- [ ] Rollback procedures tested

### Testing

- [ ] Unit tests pass (individual components)
- [ ] Integration tests pass (real external systems in test env)
- [ ] Scenario tests pass (end-to-end workflows)
- [ ] Load tests pass (concurrent workflow execution)
- [ ] Chaos tests pass (external system failures)

---

## Related Documentation

- **[Orchestrator Interface](../orchestrator/README.md)** - Formal specification for lifecycle, errors, routing
- **[System Execution Narrative](../SYSTEM_EXECUTION_NARRATIVE.md)** - Complete request → response flow
- **[Failure Modes](../orchestrator/FAILURE_MODES.md)** - Error taxonomy and retry semantics
- **[Scenario Testing](../testing/SCENARIO_TESTING.md)** - End-to-end test patterns

---

**For questions or contributions, see [CONTRIBUTING.md](../../CONTRIBUTING.md).**
