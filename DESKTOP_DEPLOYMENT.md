# Desktop Deployment Guide for Sales Reps

**CUGAr Sales Assistant - Local Installation & Launch**

This guide helps sales representatives and technical specialists deploy CUGAr Sales Assistant on their local machines for offline-first sales automation.

---

## 🎯 What You Get

- **Territory Planning**: Analyze coverage, identify gaps, simulate changes
- **Account Intelligence**: Score prospects, research companies, find decision makers
- **Smart Outreach**: Draft emails, create sequences, use templates
- **Deal Qualification**: BANT/MEDDIC scoring, risk assessment
- **Offline-First**: Works without internet, syncs when available

---

## 📋 Prerequisites

### Required Software

1. **Python 3.9+**
   - Download: https://www.python.org/downloads/
   - Verify: Open terminal/command prompt and run `python3 --version`

2. **Node.js 18+**
   - Download: https://nodejs.org/
   - Verify: Run `node --version`

3. **Git** (for cloning repository)
   - Download: https://git-scm.com/

### System Requirements

- **OS**: Windows 10+, macOS 11+, or Linux (Ubuntu 20.04+)
- **RAM**: 4GB minimum, 8GB recommended
- **Storage**: 2GB free space
- **Network**: Internet for initial setup and optional CRM sync

---

## 🚀 Quick Start (5 Minutes)

### Option 1: Simple Launch Scripts (Recommended)

#### **macOS / Linux**

```bash
# 1. Clone repository
git clone https://github.com/your-org/CUGAr-SALES.git
cd CUGAr-SALES

# 2. Run launcher (handles everything)
./launch_sales_assistant.sh
```

#### **Windows**

```cmd
# 1. Clone repository
git clone https://github.com/your-org/CUGAr-SALES.git
cd CUGAr-SALES

# 2. Double-click or run
launch_sales_assistant.bat
```

**What it does:**
- ✓ Checks dependencies
- ✓ Runs first-time setup wizard (if needed)
- ✓ Installs Python/Node packages
- ✓ Starts backend server
- ✓ Opens UI in browser
- ✓ Loads demo data automatically

---

### Option 2: Desktop App (Best User Experience)

Build a native desktop application that sales reps can launch like any other app:

#### **Build Desktop App**

```bash
# Navigate to frontend
cd src/frontend_workspaces/agentic_chat

# Install dependencies
npm install

# Build desktop app for your platform
npm run electron:build          # Auto-detect platform
npm run electron:build:mac      # macOS (Intel & Apple Silicon)
npm run electron:build:win      # Windows
npm run electron:build:linux    # Linux (AppImage & .deb)
```

**Installers are created in:** `dist-electron/`

#### **Distribute to Sales Team**

- **macOS**: Share the `.dmg` file
- **Windows**: Share the `.exe` installer
- **Linux**: Share the `.AppImage` or `.deb` file

Sales reps just:
1. Download installer
2. Double-click to install
3. Launch "CUGAr Sales Assistant" from Applications/Start Menu
4. Complete 2-minute setup wizard on first run

---

## 🎓 First-Time Setup Wizard

On first launch, you'll see a quick setup wizard:

### Step 1: Profile Selection
```
Choose your sales profile:
1. Enterprise Sales Rep
2. SMB/Mid-Market Rep
3. Technical Specialist (Presales)
4. Custom
```

### Step 2: CRM Integration (Optional)
```
Connect to CRM? (optional, can skip)
- Salesforce
- HubSpot
- Mock Data (for testing)
- Skip (offline mode)
```

### Step 3: Demo Data
```
Load demo accounts for testing? (Recommended)
✓ Yes - Load IBM Sales Cloud fixtures
○ No - Start fresh
```

### Step 4: Preferences
```
Enable mock adapters? Yes (recommended for first use)
Default tools budget: 20 calls per task
Auto-save drafts: Yes
```

**Setup complete!** Configuration saved to `.env.sales`

---

## 💡 Using the Sales Assistant

### Quick Actions Panel

The UI provides **one-click access** to common workflows:

#### **Prospecting**
- "Score Prospect Fit" - Evaluate if company matches ICP
- "Research Account" - Deep dive on company + signals
- "Find Decision Makers" - Get contacts at target account

#### **Outreach**
- "Draft Cold Email" - Personalized first touch
- "Draft Follow-Up" - Contextual reply
- "Build Email Sequence" - Multi-touch campaign
- "Browse Templates" - Pre-approved messaging

#### **Qualification**
- "Qualify Opportunity" - BANT/MEDDIC scoring
- "Assess Deal Risk" - Identify blockers
- "What Should I Do Next?" - Recommended actions

#### **Planning**
- "Analyze My Territory" - Coverage gaps
- "Simulate Territory Change" - Model impact

### Example Workflow

**Goal**: Prospect a new company

1. Click **"Full Prospect Workflow"**
2. Enter company name: `Acme Corp`
3. System automatically:
   - Scores ICP fit (→ 85% match)
   - Researches company (→ recent funding, hiring)
   - Finds decision makers (→ VP Engineering)
   - Drafts personalized email (→ grade A)
4. Review draft, edit as needed
5. Click "Copy to clipboard" or export to CRM

**Time saved**: 45+ minutes of manual research

---

## 🔒 Security & Privacy

### Data Storage

- **Local-first**: All data stored on your machine
- **No cloud uploads**: Unless you explicitly connect CRM
- **Profile isolation**: Each user's data is separated
- **PII protection**: Automatic redaction in logs

### Secrets Management

Credentials stored in `.env.sales` (never in code):
```
SALESFORCE_CLIENT_ID=your_key_here
SALESFORCE_CLIENT_SECRET=your_secret_here
```

**Never commit `.env.sales` to version control!**

### Offline Mode

- Territory analysis works offline
- Message drafting uses local templates
- Account scoring runs locally
- Only CRM sync requires internet

---

## 🛠 Troubleshooting

### Backend Won't Start

**Error**: `Address already in use (port 8000)`

**Fix**: Another app is using port 8000
```bash
# Find process
lsof -ti:8000  # macOS/Linux
netstat -ano | findstr :8000  # Windows

# Kill it or change port in launch script
```

### Frontend Won't Load

**Error**: `Cannot connect to backend`

**Fix**: Backend may still be starting
```bash
# Check if backend is running
curl http://localhost:8000/health

# Wait 10 seconds, then retry
```

### Setup Wizard Fails

**Error**: `ModuleNotFoundError: No module named 'cuga'`

**Fix**: Install Python package
```bash
pip install -e .
```

### Mock Data Not Loading

**Error**: `No accounts found`

**Fix**: Re-run setup wizard
```bash
python3 -m cuga.frontend.setup_wizard
```

---

## 📦 What Gets Installed?

### Python Packages
- FastAPI (backend server)
- Uvicorn (ASGI server)
- Pydantic (data validation)
- CUGAr core libraries

### Node Packages
- React (UI framework)
- Carbon Design System (IBM UI kit)
- Vite (build tool)
- Electron (desktop wrapper)

### Total Size
~500MB installed (includes all dependencies)

---

## 🔄 Updating to Latest Version

```bash
# Pull latest changes
cd CUGAr-SALES
git pull origin main

# Update Python dependencies
pip install -e . --upgrade

# Update Node dependencies
cd src/frontend_workspaces/agentic_chat
npm install

# Rebuild desktop app (if using)
npm run electron:build
```

---

## 🎯 Sales Rep Cheat Sheet

### Daily Workflows

**Morning**: Territory Review
```
→ Click "Analyze My Territory"
→ Review coverage gaps
→ Prioritize high-fit accounts
```

**Prospecting**: New Outbound
```
→ Click "Full Prospect Workflow"
→ Enter company name
→ Review + edit draft email
→ Copy to email client
```

**Deal Management**: Qualify & Progress
```
→ Click "Qualify Opportunity"
→ Enter deal details
→ Review BANT/MEDDIC scores
→ Follow recommended next actions
```

**Follow-Up**: Nurture Sequence
```
→ Click "Build Email Sequence"
→ Define persona + value prop
→ Get 5-touch campaign
→ Schedule in CRM/calendar
```

### Keyboard Shortcuts

- `Cmd/Ctrl + K` - Quick action search
- `Cmd/Ctrl + /` - Show available tools
- `Cmd/Ctrl + N` - New conversation
- `Cmd/Ctrl + E` - Export results

---

## 🚨 Important Guardrails

The system has **built-in safety rails** to prevent accidents:

### ❌ System Will NOT
- Auto-send emails (always draft status)
- Auto-assign territories without approval
- Auto-close deals or update forecasts
- Modify pricing or legal terms

### ✓ System Will ALWAYS
- Propose actions (not execute)
- Explain reasoning
- Surface unknowns/risks
- Require human approval for changes

**Your judgment is final!** The assistant recommends; you decide.

---

## 📞 Getting Help

### Resources

- **User Guide**: `docs/sales/USER_GUIDE.md`
- **E2E Workflows**: `docs/sales/E2E_WORKFLOW_GUIDE.md`
- **Tool Reference**: `docs/sales/TOOL_REFERENCE.md`
- **FAQ**: `docs/sales/FAQ.md`

### Support Channels

- **IT Help Desk**: support@yourcompany.com
- **Sales Ops**: salesops@yourcompany.com
- **Slack**: #cugar-sales-support

### Feedback

Found a bug or have a feature request?
- File issue: https://github.com/your-org/CUGAr-SALES/issues
- Email: cugar-feedback@yourcompany.com

---

## ✅ Production Readiness Checklist

Before rolling out to your sales team:

### Pre-Launch
- [ ] Test on representative hardware (Windows/Mac/Linux)
- [ ] Validate with 5+ sales reps in pilot
- [ ] Confirm CRM integration works (if used)
- [ ] Load approved templates into system
- [ ] Configure tool budgets (default: 20 calls/task)
- [ ] Set up analytics/monitoring
- [ ] Create training materials
- [ ] Establish support process

### Launch Day
- [ ] Distribute installers via secure channel
- [ ] Schedule onboarding sessions (30 min each)
- [ ] Monitor for first-run issues
- [ ] Collect feedback in first week
- [ ] Address top pain points quickly

### Post-Launch (Week 2+)
- [ ] Analyze usage patterns
- [ ] Identify power users for case studies
- [ ] Gather feature requests
- [ ] Plan next iteration

---

## 🎊 You're Ready!

Your sales team now has:
- ✅ One-click local deployment
- ✅ Offline-first capabilities
- ✅ Pre-configured sales workflows
- ✅ Safety guardrails
- ✅ Desktop app experience

**Go close deals!** 🚀
