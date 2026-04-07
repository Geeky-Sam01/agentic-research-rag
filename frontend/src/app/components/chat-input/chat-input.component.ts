import { Component, Input, Output, EventEmitter, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Select } from 'primeng/select';
import { Textarea } from 'primeng/textarea';
import { TextareaModule } from 'primeng/textarea';
import { ButtonModule } from 'primeng/button';
import { ChatService } from '../../services/chat.service';

import { CommonModule } from '@angular/common';

@Component({
  selector: 'app-chat-input',
  standalone: true,
  imports: [CommonModule, FormsModule, ButtonModule, Select, TextareaModule],
  templateUrl: './chat-input.component.html',
  styleUrl: './chat-input.component.css'
})
export class ChatInputComponent {
  @Input() isCentered = false;
  @Output() send = new EventEmitter<{query: string, isStructured: boolean}>();

  chatService = inject(ChatService);
  inputValue = '';
  focused = signal(false);
  isStructuredMode = false;

  toggleStructuredMode(): void {
    this.isStructuredMode = !this.isStructuredMode;
  }

  get selectedModel(): string {
    return this.chatService.selectedModel();
  }

  set selectedModel(val: string) {
    this.chatService.selectedModel.set(val);
  }

  models = [
    { label: 'Auto (Free)', value: 'openrouter/free' },
    { label: 'StepFun Flash', value: 'stepfun/step-3.5-flash:free' },
    { label: 'Qwen 3.6 Plus', value: 'qwen/qwen3.6-plus:free' },
    { label: 'Nemotron-3 120B', value: 'nvidia/nemotron-3-super-120b-a12b:free' },
    { label: 'MiniMax M2.5', value: 'minimax/minimax-m2.5:free' },
    { label: 'Gemma 2 9B', value: 'google/gemma-2-9b-it:free' }
  ];

  canSend(): boolean {
    return this.inputValue.trim().length > 0 && !this.chatService.loading();
  }

  onKeydown(event: KeyboardEvent): void {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      this.sendMessage();
    }
  }

  isLarge(): boolean {
    return this.inputValue.length > 60 || this.inputValue.includes('\n');
  }

  sendMessage(): void {
    const query = this.inputValue.trim();
    if (!query || this.chatService.loading()) return;
    this.send.emit({ query, isStructured: this.isStructuredMode });
    this.inputValue = '';
  }
}
