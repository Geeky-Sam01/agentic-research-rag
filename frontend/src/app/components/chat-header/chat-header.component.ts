import { Component, inject, computed } from '@angular/core';
import { ChatService } from '../../services/chat.service';
import { UiStateService } from '../../services/ui-state.service';
import { ChatHistoryService } from '../../services/chat-history.service';
import { ButtonModule } from 'primeng/button';
import { Tooltip } from 'primeng/tooltip';

@Component({
  selector: 'app-chat-header',
  standalone: true,
  imports: [ButtonModule, Tooltip],
  templateUrl: './chat-header.component.html'
})
export class ChatHeaderComponent {
  chatService = inject(ChatService);
  uiState = inject(UiStateService);
  historyService = inject(ChatHistoryService);

  currentTitle = computed(() => {
    const id = this.historyService.currentSessionId();
    if (!id) return 'New Conversation';
    const session = this.historyService.sessions().find(s => s.id === id);
    return session?.title ?? 'New Conversation';
  });
}
