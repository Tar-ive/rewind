# Dev B Tasks: Frontend & Automation (Rewind Spec v2)

This document outlines the tasks for Developer B, focusing on the frontend UI, voice input, and browser automation via GhostWorker.

## Phase 1: Foundation (Hours 0–6)

### 1.1 Frontend Infrastructure (Hours 0-1)
- [ ] Initialize Next.js repository.
- [ ] Configure TailwindCSS.
- [ ] Deploy initial scaffold to Vercel.
- [ ] Provide WebSocket client skeleton for real-time updates.

### 1.2 Core UI Components (Hours 1-3)
- [ ] Implement **Task Card** components.
    - [ ] Priority indicators (P0/red, P1/orange, P2/blue, P3/gray).
- [ ] Implement **Schedule Day-View** layout ("River Timeline").
- [ ] Connect WebSocket to receive `UpdatedSchedule` events.

### 1.3 Split Screen & Voice (Hours 3-6)
- [ ] Implement **Schedule Swap Animations**.
    - [ ] Task cards sliding in/out with color transitions.
- [ ] Implement **Split-Screen Layout**:
    - [ ] Left: Schedule View.
    - [ ] Right: Agent Activity Log / GhostWorker View.
- [ ] Implement **Voice Input** using Web Speech API.
    - [ ] Send voice commands to backend.

---
**[CHECKPOINT 1 - Phase 1 Complete]**
- **Test Integration**: Verify voice input sends commands to backend.
- **Sync**: Merge frontend components to `main`.
- **Verify**: Basic UI renders schedule data and updates via WebSocket.
---

## Phase 2: Core Intelligence (Hours 6–18)

### 2.1 GhostWorker Automation - Basic (Hours 6-10)
- [ ] Set up **Stagehand (Browserbase) + Headless Chrome**.
- [ ] Implement **Gmail Automation**:
    - [ ] Open compose window.
    - [ ] Fill recipient/subject.
    - [ ] Write draft body.
- [ ] Integrate live browser session view into split-screen (Right Panel).
- [ ] Create **Draft Review UI Component**.

### 2.2 GhostWorker Expansion (Hours 10-14)
- [ ] Implement **Slack Automation**:
    - [ ] Navigate to channel/DM.
    - [ ] Draft message.
- [ ] Implement **Notion/Doc Updates**.
- [ ] Implement **Appointment Cancellation Flow**:
    - [ ] Navigate provider site -> Find cancel button -> Execute.
- [ ] Enhance **Draft Approval Flow** in UI (Approve/Edit/Reject buttons).

### 2.3 Full Pipeline Integration (Hours 14-18)
- [ ] **Full Frontend Integration**:
    - [ ] Trigger: Disruption event to frontend.
    - [ ] Action: Schedule redraw + swap animation.
    - [ ] Action: GhostWorker activity panel updates live.
- [ ] **UI Polish Pass 1**: Spacing, typography, empty states, loading states.

---
**[CHECKPOINT 2 - Phase 2 Complete]**
- **Test Integration**: Verify GhostWorker effectively controls browser based on backend commands.
- **Sync**: Merge automation scripts and UI updates to `main`.
- **Verify**: Full demo loop works: Disruption -> Schedule Change -> GhostWorker Draft -> User Approve.
---

## Phase 3: Polish & Prize Lock (Hours 18–30)

### 3.1 UI Refinement (Hours 18-22)
- [ ] Implement smooth easing for swap animations.
- [ ] Refine priority color system.
- [ ] Add **Energy Indicator** component.
- [ ] Add **Time-Saved Counter**.
- [ ] Ensure mobile responsiveness.
- [ ] Implement **Dark Mode**.
- [ ] Enhance Agent Activity Log with real-time updates.

### 3.2 Advanced Automation & Edge Cases (Hours 22-26)
- [ ] (Stretch) Implement **Uber Booking Automation**.
- [ ] (Stretch) Implement **Calendar Rescheduling Automation**.
- [ ] **Demo Flow Scripting**:
    - [ ] Set up exact scenario data (Sarah’s schedule).
    - [ ] Create timed calendar change trigger.

### 3.3 Rehearsal & Support (Hours 26-30)
- [ ] **Demo Rehearsal x5**.
- [ ] Fix frontend bugs found during rehearsal.
- [ ] Create **Devpost Content**:
    - [ ] Screenshots.
    - [ ] Architecture diagram.
    - [ ] Description.

---
**[CHECKPOINT 3 - Phase 3 Complete]**
- **Verification**: UI looks polished and professional ("Premium Design").
- **Sync**: Frontend code freeze.
---

## Phase 4: Ship (Hours 30–36)

- [ ] (Hours 30-32) Final frontend bug fixes. Record backup demo video (screen + voice).
- [ ] (Hours 32-34) Write Devpost submission. Add Innovation Lab badges to README.
- [ ] (Hours 34-36) Final demo rehearsals. Submit Devpost.
