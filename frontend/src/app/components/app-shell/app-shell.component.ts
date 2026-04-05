import { Component, inject, HostListener } from '@angular/core';
import { LeftPanelComponent } from '../left-panel/left-panel.component';
import { ChatPanelComponent } from '../chat-panel/chat-panel.component';
import { RightPanelComponent } from '../right-panel/right-panel.component';
import { UiStateService } from '../../services/ui-state.service';
import { ChatService } from '../../services/chat.service';
import { ChatHistoryService } from '../../services/chat-history.service';
import { Toast } from 'primeng/toast';

@Component({
  selector: 'app-shell',
  standalone: true,
  imports: [
    LeftPanelComponent,
    ChatPanelComponent,
    RightPanelComponent,
    Toast
  ],
  templateUrl: './app-shell.component.html',
  styleUrl: './app-shell.component.css'
})
export class AppShellComponent {
  uiState = inject(UiStateService);
  chatService = inject(ChatService);
  historyService = inject(ChatHistoryService);

  @HostListener('window:keydown', ['$event'])
  handleKeyboardEvent(event: KeyboardEvent) {
    const key = event.key.toLowerCase();
    
    // Ctrl + Alt + B -> Toggle Evidence
    if (event.ctrlKey && event.altKey && key === 'b') {
      event.preventDefault();
      this.uiState.toggleEvidence();
    } 
    // Ctrl + B -> Toggle Chat History
    else if (event.ctrlKey && key === 'b') {
      event.preventDefault();
      this.uiState.toggleHistory();
    }
  }

  newChat(): void {
    this.chatService.clearMessages();
    this.historyService.createNewChat();
  }

  loadChat(id: string): void {
    this.chatService.loadSession(id);
  }

  deleteChat(event: Event, id: string): void {
    event.stopPropagation();
    this.historyService.deleteSession(id);
  }
}
