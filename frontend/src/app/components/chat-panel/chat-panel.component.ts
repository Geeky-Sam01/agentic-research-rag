import { Component, inject } from '@angular/core';
import { ChatHeaderComponent } from '../chat-header/chat-header.component';
import { MessageListComponent } from '../message-list/message-list.component';
import { ChatInputComponent } from '../chat-input/chat-input.component';
import { ChatService } from '../../services/chat.service';
import { DocumentService } from '../../services/document.service';

@Component({
  selector: 'app-chat-panel',
  standalone: true,
  imports: [ChatHeaderComponent, MessageListComponent, ChatInputComponent],
  templateUrl: './chat-panel.component.html',
  styleUrl: './chat-panel.component.css'
})
export class ChatPanelComponent {
  chatService = inject(ChatService);
  docService = inject(DocumentService);

  onSend(query: string): void {
    this.chatService.sendQuery(query);
  }
}
