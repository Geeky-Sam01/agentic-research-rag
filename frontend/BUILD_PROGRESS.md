# RAG UI Build Progress

## Phase 0 — Foundation
- [x] PrimeNG 21.1.5 installed
- [x] @primeuix/themes installed
- [x] @angular/cdk installed
- [ ] app.config.ts — providePrimeNG + HttpClient + Animations
- [ ] angular.json — add primeicons CSS
- [ ] styles.css — color tokens + body reset

## Phase 1 — Models
- [ ] src/app/models/chat.models.ts

## Phase 2 — Services
- [ ] src/app/services/chat.service.ts
- [ ] src/app/services/document.service.ts
- [ ] src/app/services/ui-state.service.ts

## Phase 3 — App Shell
- [ ] app-shell component (layout wrapper)
- [ ] app.ts + app.html updated

## Phase 4 — Left Panel ⬅️ CURRENT
- [ ] source-item.component
- [ ] source-list.component
- [ ] left-panel.component

## Phase 5 — Chat Panel (Center) ⬅️ CURRENT
- [ ] chat-header.component
- [ ] chat-input.component
- [ ] message-item.component
- [ ] message-list.component
- [ ] citations.component (placeholder)
- [ ] chat-panel.component

## Phase 6 — Right Panel (Evidence)
- [ ] chunk-item.component
- [ ] evidence-viewer.component
- [ ] right-panel.component

## Phase 7 — Backend: Add sources to SSE stream
- [ ] backend/app/api/chat.py

## Phase 8 — Mobile
- [ ] Drawer (sources)
- [ ] Dialog (evidence)

## Legend
- [x] Done
- [ ] Pending
- [~] In progress
