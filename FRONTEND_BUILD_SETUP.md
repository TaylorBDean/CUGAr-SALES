# Frontend Build & Deployment Setup

## Quick Setup for Testing

Since this is an npm workspaces monorepo, follow these steps:

### 1. Install All Dependencies
```bash
# From project root
cd /home/taylor/CUGAr-SALES

# Install Python dependencies
pip install -e .

# Install frontend dependencies (from workspace root)
cd src/frontend_workspaces
npm install
```

### 2. Development Mode (Recommended)
```bash
# Use the launch script (easiest)
./launch_sales_assistant.sh

# Or manually:
# Terminal 1 - Backend
python3 -m uvicorn cuga.backend.server.main:app --port 8000

# Terminal 2 - Frontend (dev mode, no build needed)
cd src/frontend_workspaces/agentic_chat
npm run dev
```

### 3. Test Quick Actions
Once running:
1. Open http://localhost:3000
2. Start a chat session
3. Press `Cmd/Ctrl + K` or click the blue lightning bolt (⚡) button
4. Try "Score Prospect Fit" action
5. Verify backend status shows green in status bar

### 4. Build Desktop App (Optional)
```bash
cd src/frontend_workspaces/agentic_chat

# First ensure all workspace deps are installed
cd ..
npm install

# Then build
cd agentic_chat
npm run electron:build
```

## Verification Checklist

### ✅ Backend Ready
```bash
# Check backend runs
python3 -m uvicorn cuga.backend.server.main:app --port 8000

# Should see: "Application startup complete"
# Test: curl http://localhost:8000/health
```

### ✅ Frontend Ready
```bash
# Check frontend dev server runs
cd src/frontend_workspaces/agentic_chat
npm run dev

# Should see: "Local: http://localhost:3000"
```

### ✅ Quick Actions Work
- [ ] FAB button visible (blue lightning bolt, bottom-right)
- [ ] Cmd/Ctrl+K opens Quick Actions panel
- [ ] Can browse 15 pre-configured actions
- [ ] Clicking action opens context input modal
- [ ] Submitting action sends prompt to chat

### ✅ Backend Status Works
- [ ] Status bar shows "Backend Ready" (green)
- [ ] Stops backend → status changes to "Backend Offline" (red)
- [ ] Restarts backend → status returns to green

### ✅ Keyboard Shortcuts Work
- [ ] Cmd/Ctrl+K toggles Quick Actions
- [ ] Cmd/Ctrl+B toggles left sidebar
- [ ] Shortcuts work from anywhere (not just in input)

## Known Issues

### Issue: npm workspace protocol error
**Symptom**: `npm error Unsupported URL Type "workspace:"`

**Cause**: Need to install from workspace root, not individual package

**Fix**:
```bash
cd src/frontend_workspaces  # NOT agentic_chat
npm install
```

### Issue: TypeScript compiler not found
**Symptom**: `tsc: not found`

**Cause**: devDependencies not installed

**Fix**: Run `npm install` from workspace root

### Issue: Quick Actions don't send message
**Symptom**: Action opens modal, but prompt doesn't send

**Current Status**: Prompt appears in chat input, press Enter manually

**Planned Fix**: Expose `sendMessage` method from CustomChat component

## Production Deployment

### Option 1: Launch Scripts (Simplest)
Distribute `launch_sales_assistant.sh` (Mac/Linux) or `.bat` (Windows).

**Pros**: No build needed, works immediately
**Cons**: Requires Python & Node.js installed

### Option 2: Electron Desktop App (Best UX)
Build native installers for each platform.

**Pros**: Single-click install, native app experience
**Cons**: Larger file size (~200MB), build time

### Option 3: Docker Container
Package everything in a container.

**Pros**: Consistent environment, easy updates
**Cons**: Requires Docker, more complex for non-technical users

## Recommended for Sales Reps

**For pilot (5-10 users)**: Launch scripts
- Fast to distribute
- Easy to update (git pull)
- Troubleshooting is easier

**For production (50+ users)**: Electron desktop app
- Professional installer
- Auto-updates
- System tray integration
- No terminal exposure

## Next Steps

1. **Test Now**: Run `./launch_sales_assistant.sh`
2. **Verify**: Press Cmd/Ctrl+K, try a quick action
3. **Pilot**: Distribute to 5 sales reps for feedback
4. **Iterate**: Fix any issues found
5. **Production**: Build installers, train team, launch!

---

**Status**: Ready for immediate testing in development mode!
