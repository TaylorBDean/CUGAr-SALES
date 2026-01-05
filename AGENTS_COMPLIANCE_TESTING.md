# AGENTS.md Compliance Features - Testing Guide

**Purpose**: Comprehensive testing guide for all newly integrated AGENTS.md compliance components  
**Date**: 2026-01-04  
**Estimated Time**: 10-15 minutes (smoke test), 1-2 hours (full validation)

---

## Prerequisites

- Backend server running on port 8000
- Frontend application accessible
- Browser with DevTools available
- curl or Postman for API testing

---

## Quick Smoke Test (10 minutes)

### 1. Start Backend
```bash
cd /home/taylor/CUGAr-SALES
python3 -m uvicorn src.cuga.backend.server.main:app --port 8000 --reload
```

Look for: `✅ Capability health endpoints registered`

### 2. Test Backend Endpoints
```bash
# Test capability status
curl http://localhost:8000/api/capabilities/status

# Test profile endpoint
curl http://localhost:8000/api/profile

# Test profile change
curl -X POST http://localhost:8000/api/profile \
  -H "Content-Type: application/json" \
  -d '{"profile_id": "smb"}'
```

### 3. Open Frontend
Navigate to http://localhost:3000 (or your frontend URL)

### 4. Visual Checks
- [ ] Status bar visible at bottom
- [ ] Budget indicators present (left side)
- [ ] Profile selector visible (center)
- [ ] "Health" and "Traces" buttons visible (right side)
- [ ] Quick Actions FAB visible (bottom right)

### 5. Interaction Checks
- [ ] Click "Health" → Modal opens with capability status
- [ ] Press Ctrl/Cmd+T → Trace viewer opens
- [ ] Click profile selector → Dropdown shows 3 profiles
- [ ] Select different profile → Change persists after reload

---

## Component-by-Component Testing

### A. BudgetIndicator

**Location**: Status bar, left side

**Tests**:
1. **Initial Render**
   ```javascript
   // Browser console
   // Should see budget indicators like "CRM: 5/20"
   document.querySelectorAll('.budget-indicator').length; // Should be > 0
   ```

2. **Color Coding**
   - Green: Usage < 70%
   - Yellow: Usage 70-90%
   - Red: Usage > 90% with warning

3. **Real-time Updates**
   - Open Network tab in DevTools
   - Watch for requests to `/api/budgets` every 5 seconds
   - Verify indicators update with new data

4. **Mock Data Fallback**
   - Stop backend server
   - Verify indicators still show mock data
   - No console errors

**Pass Criteria**: ✅ Indicators visible, color-coded correctly, update every 5s

---

### B. ProfileSelector

**Location**: Status bar, center

**Tests**:
1. **Initial Display**
   ```javascript
   // Browser console
   localStorage.getItem('cuga_profile'); // Should return 'enterprise' (default)
   ```

2. **Profile Switching**
   - Click profile selector
   - Verify 3 options: Enterprise, SMB, Technical Specialist
   - Click "SMB"
   - Verify selection changes in UI
   - Check localStorage: `localStorage.getItem('cuga_profile')` → 'smb'

3. **Persistence**
   - Switch to "Technical Specialist"
   - Refresh page (F5)
   - Verify "Technical Specialist" still selected

4. **Backend Integration**
   - Open Network tab
   - Switch profile
   - Verify POST request to `/api/profile` with correct payload

**Pass Criteria**: ✅ 3 profiles selectable, persists across reloads, backend notified

---

### C. CapabilityStatus

**Location**: Modal opened by "Health" button

**Tests**:
1. **Open Modal**
   - Click "⚙ Health" button in status bar
   - Verify modal appears with overlay
   - Verify clicking overlay closes modal

2. **Capability Display**
   - Capabilities grouped by domain (territory, intelligence, engagement, etc.)
   - Each shows: name, status (online/degraded/offline), mode (mock/live)
   - Status icons color-coded (green=online, yellow=degraded, red=offline)

3. **Auto-refresh**
   - Leave modal open for 30+ seconds
   - Verify "Last updated" timestamp changes
   - Open Network tab, should see requests every 30s

4. **Manual Refresh**
   - Click refresh button in header
   - Verify timestamp updates immediately
   - Verify loading spinner appears briefly

5. **Compact Mode** (if implemented in status bar)
   - Check status bar for compact capability indicator
   - Should show "X/Y capabilities"
   - Click to expand full panel

**Pass Criteria**: ✅ Modal displays capabilities, groups by domain, auto-refreshes

---

### D. TraceViewer

**Location**: Modal opened by "Traces" button or Ctrl/Cmd+T

**Tests**:
1. **Keyboard Shortcut**
   - Press Ctrl+T (Windows/Linux) or Cmd+T (Mac)
   - Verify trace viewer modal opens

2. **Timeline Display**
   - Start a conversation to generate traces
   - Open trace viewer
   - Verify events listed chronologically
   - Each event shows: timestamp, event type, status, duration

3. **Event Expansion**
   - Click an event to expand
   - Verify details shown (metadata, parameters)
   - Verify JSON formatting readable

4. **Status Indicators**
   - Success events: Green checkmark
   - Error events: Red X
   - Running events: Blue spinner
   - Pending events: Gray circle

5. **Trace Statistics**
   - Header shows total duration
   - Header shows event count
   - Filter by event type works

**Pass Criteria**: ✅ Traces display in timeline, expandable, color-coded by status

---

### E. ApprovalDialog

**Location**: Modal overlay (appears on high-risk action)

**Tests**:
1. **Trigger Approval** (via browser console):
   ```javascript
   window.dispatchEvent(new CustomEvent('approval-requested', {
     detail: {
       requestId: 'test_001',
       action: 'send_email',
       riskLevel: 'high',
       description: 'Send email to executive contact',
       toolName: 'send_outbound_email',
       reasoning: 'User requested to send pricing proposal',
       consequences: [
         'Email will be sent immediately',
         'Cannot be undone',
         'Recipient will be notified'
       ],
       parameters: {
         to: 'ceo@acme.com',
         subject: 'Pricing Proposal',
         body: 'Dear CEO, ...'
       }
     }
   }));
   ```

2. **Visual Verification**
   - Risk badge displays "HIGH" in red
   - Tool name shown: `send_outbound_email`
   - Action description clear
   - All 3 consequences listed
   - Parameters shown in formatted preview

3. **User Actions**
   - Click "Approve" → Dialog closes, console shows POST to `/api/approve`
   - Trigger again, click "Reject" → Dialog closes with rejection
   - Trigger again, click "Cancel" → Dialog closes, no API call

4. **Risk Levels**
   - Test with `riskLevel: 'low'` → Green badge
   - Test with `riskLevel: 'medium'` → Yellow badge
   - Test with `riskLevel: 'high'` → Red badge

**Pass Criteria**: ✅ Dialog appears, risk level clear, all actions work

---

### F. ErrorRecovery

**Location**: Modal overlay (appears on error)

**Tests**:
1. **Trigger Error** (simulate in code or console):
   ```javascript
   // Assuming setErrorState is accessible via React DevTools
   // Or modify App.tsx temporarily to add a test button
   setErrorState({
     error: new Error('Database connection timeout after 30 seconds'),
     failureMode: 'RESOURCE',
     partialResult: {
       completed: ['fetch_accounts', 'enrich_data'],
       failed: ['update_crm'],
       data: {
         accounts: [
           { name: 'Acme Corp', score: 85 },
           { name: 'TechStart Inc', score: 72 }
         ]
       }
     }
   });
   ```

2. **Visual Verification**
   - Failure mode badge: "Resource Unavailable" (yellow for RESOURCE)
   - Error message displayed clearly
   - Completed steps: "fetch_accounts", "enrich_data" (green checkmarks)
   - Failed steps: "update_crm" (red X)
   - Recommendation: "Retry in a few moments"

3. **Partial Results**
   - "View partial data" expandable section
   - JSON formatted and readable
   - Shows account data

4. **Actions**
   - "Retry" button enabled (RESOURCE is retryable)
   - "Use Partial Results" button enabled
   - "Cancel" button present
   - Click each, verify dialog closes appropriately

5. **Failure Modes** (test each):
   - AGENT → Yellow, retryable
   - SYSTEM → Red, maybe not retryable
   - RESOURCE → Yellow, retryable
   - POLICY → Red, not retryable
   - USER → Blue, fix input and retry

**Pass Criteria**: ✅ Error displayed, failure mode clear, partial results accessible

---

## Integration Testing Scenarios

### Scenario 1: Full Approval Workflow
```
1. User: "Send pricing email to john@acme.com"
2. System detects high-risk action (email send)
3. ApprovalDialog appears with:
   - Risk: HIGH
   - Action: send_email
   - Consequences listed
4. User clicks "Approve" with feedback: "Pricing approved by manager"
5. Dialog closes
6. Email sent (check backend logs)
7. Trace event logged: "approval_received"
8. Budget indicator updates: Email budget +1
```

**Validation**:
- [ ] Approval dialog appeared
- [ ] Risk level displayed correctly
- [ ] Feedback collected
- [ ] Backend received approval
- [ ] Trace logged
- [ ] Budget updated

### Scenario 2: Error Recovery with Partial Results
```
1. User: "Analyze all accounts in West region"
2. System fetches 50 accounts successfully
3. CRM API times out on account 51
4. ErrorRecovery dialog appears:
   - Failure mode: RESOURCE
   - Completed: 50 accounts fetched
   - Failed: 1 account fetch
   - Partial data: 50 account objects
5. User clicks "Use Partial Results"
6. System displays table with 50 accounts
7. Budget charged for 50 successful operations
```

**Validation**:
- [ ] Error dialog appeared
- [ ] Failure mode correct (RESOURCE)
- [ ] Completed vs failed steps clear
- [ ] Partial data accessible
- [ ] User could use partial results
- [ ] Budget reflected actual work done

### Scenario 3: Profile Switch with Capability Change
```
1. Current profile: Enterprise (strategic tools enabled)
2. User switches to: SMB (velocity tools enabled)
3. Profile selector updates
4. localStorage updated
5. Backend notified via POST /api/profile
6. Capability status refreshes
7. Budgets change to SMB limits
8. Quick Actions update to SMB workflows
```

**Validation**:
- [ ] Profile changed in UI
- [ ] localStorage persisted
- [ ] Backend received profile change
- [ ] Capability status updated
- [ ] Budget limits changed
- [ ] Quick Actions updated

---

## Performance Testing

### Metrics to Monitor

1. **Component Render Times**
   ```javascript
   // React DevTools > Profiler
   // Record session, interact with components
   // Target: <100ms per component render
   ```

2. **Network Activity**
   ```
   Budget polling: Every 5s (check Network tab)
   Capability health: Every 30s
   Profile change: On-demand
   Approval: On-demand
   ```

3. **Memory Usage**
   ```javascript
   console.log(performance.memory);
   // Monitor over 5-10 minutes
   // Should not grow unbounded
   ```

### Performance Pass Criteria
- [ ] Initial page load <3s
- [ ] Component render <100ms
- [ ] Modal open/close <50ms
- [ ] Budget update <200ms
- [ ] No memory leaks over 10 minutes

---

## Regression Testing

Before deploying, verify existing features still work:

- [ ] Quick Actions panel opens (Cmd/Ctrl+K)
- [ ] Chat messages send and receive
- [ ] Left sidebar toggles (Cmd/Ctrl+B)
- [ ] Workspace panel functions
- [ ] File autocomplete works
- [ ] Status bar displays backend status
- [ ] No console errors on page load

---

## Browser Compatibility

Test in:
- [ ] Chrome (latest)
- [ ] Firefox (latest)
- [ ] Safari (latest)
- [ ] Edge (latest)

Known issues:
- Styled-jsx may require polyfill in older browsers
- Keyboard shortcuts may conflict with browser shortcuts

---

## Accessibility Testing

- [ ] All modals focusable and keyboard navigable
- [ ] Tab order logical
- [ ] Escape key closes modals
- [ ] Screen reader friendly (ARIA labels)
- [ ] Color contrast meets WCAG AA standards
- [ ] Focus indicators visible

---

## Error Conditions to Test

1. **Backend Unavailable**
   - Stop backend server
   - Verify components use mock data
   - Verify user-friendly error messages

2. **Network Slow**
   - Throttle network to "Slow 3G" in DevTools
   - Verify loading indicators appear
   - Verify no timeouts or crashes

3. **Malformed Data**
   - Mock endpoint returning invalid JSON
   - Verify graceful error handling
   - Verify fallback to safe defaults

4. **Large Datasets**
   - Mock 1000+ trace events
   - Verify trace viewer performance
   - Verify scroll and virtualization

---

## Sign-off Checklist

Before marking testing complete:

### Functional
- [ ] All 7 components render without errors
- [ ] All user interactions work as expected
- [ ] Backend endpoints return correct data
- [ ] Event listeners trigger appropriately
- [ ] State updates reflected in UI

### Visual
- [ ] Styling consistent across components
- [ ] Colors match design system
- [ ] Icons display correctly
- [ ] Text readable at all sizes
- [ ] Responsive on mobile (if applicable)

### Performance
- [ ] No performance regressions
- [ ] Network activity reasonable
- [ ] Memory usage stable
- [ ] No console errors or warnings

### Documentation
- [ ] Integration guide reviewed
- [ ] Known issues documented
- [ ] User workflows documented
- [ ] Testing results recorded

---

## Reporting Issues

For any bugs found:

1. **Severity**:
   - Critical: Blocks core functionality
   - High: Major feature broken
   - Medium: Minor feature issue
   - Low: Cosmetic/polish

2. **Information to Include**:
   - Browser and version
   - Steps to reproduce
   - Expected vs actual behavior
   - Screenshots/video
   - Console errors
   - Network activity

3. **Where to Report**:
   - Create issue in project tracker
   - Tag with "agents-compliance"
   - Assign to appropriate team member

---

## Success Criteria

Testing is complete when:

✅ All smoke tests pass  
✅ All component tests pass  
✅ All integration scenarios work  
✅ Performance acceptable  
✅ No critical or high-severity bugs  
✅ Documentation updated  
✅ Team sign-off obtained

---

## Next Steps After Testing

1. Deploy to staging environment
2. Conduct user acceptance testing (UAT)
3. Address feedback and iterate
4. Deploy to production
5. Monitor golden signals (success rate, latency, errors)

---

**Testing Guide Version**: 1.0  
**Last Updated**: 2026-01-04  
**Maintained By**: CUGAr Engineering Team
