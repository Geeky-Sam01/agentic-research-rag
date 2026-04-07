import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ChatHistoryService } from '../../services/chat-history.service';
import { UiStateService } from '../../services/ui-state.service';
import { ChatService } from '../../services/chat.service';
import { ButtonModule } from 'primeng/button';
import { TooltipModule } from 'primeng/tooltip';

@Component({
  selector: 'app-left-panel',
  standalone: true,
  imports: [CommonModule, ButtonModule, TooltipModule],
  templateUrl: './left-panel.component.html',
  styleUrl: './left-panel.component.css'
})
export class LeftPanelComponent {
  public historyService = inject(ChatHistoryService);
  public uiState = inject(UiStateService);
  private chatService = inject(ChatService);

  newChat() {
    this.chatService.clearMessages();
    this.historyService.createNewChat();
  }

  loadChat(id: string) {
    this.chatService.loadSession(id);
  }

  deleteChat(event: Event, id: string) {
    event.stopPropagation();
    if (confirm('Delete this chat permanently?')) {
      this.historyService.deleteSession(id);
    }
  }
}
