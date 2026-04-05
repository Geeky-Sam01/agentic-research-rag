import { Component, inject } from '@angular/core';
import { ChatService } from '../../services/chat.service';
import { UiStateService } from '../../services/ui-state.service';
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
}
