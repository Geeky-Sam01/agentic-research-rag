import { Component, Input, Output, EventEmitter, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Textarea } from 'primeng/textarea';
import { ButtonModule } from 'primeng/button';
import { ChatService } from '../../services/chat.service';

@Component({
  selector: 'app-chat-input',
  standalone: true,
  imports: [FormsModule, Textarea, ButtonModule],
  templateUrl: './chat-input.component.html',
  styleUrl: './chat-input.component.css'
})
export class ChatInputComponent {
  @Input() isCentered = false;
  @Output() send = new EventEmitter<string>();

  chatService = inject(ChatService);
  inputValue = '';
  focused = signal(false);

  canSend(): boolean {
    return this.inputValue.trim().length > 0 && !this.chatService.loading();
  }

  onKeydown(event: KeyboardEvent): void {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      this.sendMessage();
    }
  }

  sendMessage(): void {
    const query = this.inputValue.trim();
    if (!query || this.chatService.loading()) return;
    this.send.emit(query);
    this.inputValue = '';
  }
}
