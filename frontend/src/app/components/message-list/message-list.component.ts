import { Component, inject, ElementRef, ViewChild, AfterViewChecked } from '@angular/core';
import { ChatService } from '../../services/chat.service';
import { MessageItemComponent } from '../message-item/message-item.component';
import { Skeleton } from 'primeng/skeleton';

@Component({
  selector: 'app-message-list',
  standalone: true,
  imports: [MessageItemComponent],
  templateUrl: './message-list.component.html',
  styleUrl: './message-list.component.css'
})
export class MessageListComponent implements AfterViewChecked {
  @ViewChild('scrollAnchor') private scrollAnchor!: ElementRef;

  chatService = inject(ChatService);

  examplePrompts = [
    'Summarize the key findings…',
    'What are the main concepts?',
    'Explain the methodology used',
    'What conclusions are drawn?'
  ];

  showScrollButton = false;
  private lastMsgCount = 0;
  private lastLoadingState = false;

  ngAfterViewChecked(): void {
    const msgs = this.chatService.messages();
    const loading = this.chatService.loading();
    const hasStreaming = msgs.some((m: any) => m.isStreaming);

    // Auto-scroll when messages change or while streaming
    if (msgs.length !== this.lastMsgCount || (hasStreaming && loading !== this.lastLoadingState)) {
      this.scrollToBottom();
      this.lastMsgCount = msgs.length;
      this.lastLoadingState = loading;
    }
  }

  usePrompt(prompt: string): void {
    // Emit via a custom event so chat-panel catches it
    const el = document.querySelector('app-chat-input textarea') as HTMLTextAreaElement;
    if (el) {
      // Set value + trigger input event
      const nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value')?.set;
      nativeInputValueSetter?.call(el, prompt);
      el.dispatchEvent(new Event('input', { bubbles: true }));
      el.focus();
    }
  }

  onScroll(event: Event): void {
    const target = event.target as HTMLElement;
    const distFromBottom = target.scrollHeight - target.scrollTop - target.clientHeight;
    // Show button if scrolled up more than 100px from the bottom
    this.showScrollButton = distFromBottom > 100;
  }

  scrollToBottom(force: boolean = false): void {
    try {
      this.scrollAnchor?.nativeElement?.scrollIntoView({ behavior: 'smooth', block: 'end' });
      if (force) {
        this.showScrollButton = false;
      }
    } catch { /* ignore */ }
  }
}
