import { Component, Input, inject, signal, OnInit, OnChanges, SimpleChanges } from '@angular/core';
import { Message, Citation } from '../../models/chat.models';
import { CitationsComponent } from '../citations/citations.component';
import { ChatService } from '../../services/chat.service';
import { UiStateService } from '../../services/ui-state.service';
import { Skeleton } from 'primeng/skeleton';
import { ButtonModule } from 'primeng/button';
import { Tooltip } from 'primeng/tooltip';
import { MarkdownComponent } from 'ngx-markdown';
import { StructuredResponseComponent } from '../structured-response/structured-response.component';

@Component({
  selector: 'app-message-item',
  standalone: true,
  imports: [CitationsComponent, Skeleton, ButtonModule, Tooltip, MarkdownComponent, StructuredResponseComponent],
  templateUrl: './message-item.component.html',
  styleUrl: './message-item.component.css'
})
export class MessageItemComponent implements OnInit, OnChanges {
  @Input({ required: true }) message!: Message;

  chatService = inject(ChatService);
  uiState = inject(UiStateService);
  copied = false;
  showThoughts = signal(false);
  private manuallyToggled = false;

  ngOnInit() {
    // Initial auto-expand if streaming and empty
    this.checkAutoExpand();
  }

  ngOnChanges(changes: SimpleChanges) {
    if (changes['message']) {
      // If content starts arriving and we haven't manually toggled, auto-collapse
      if (this.message.content.length > 0 && !this.manuallyToggled && this.showThoughts()) {
        this.showThoughts.set(false);
      }
      
      // If a message was reset or a new one started
      if (this.message.content.length === 0 && this.message.isStreaming) {
        this.checkAutoExpand();
      }
    }
  }

  private checkAutoExpand() {
    if (this.message.isStreaming && this.message.content.length === 0 && !this.manuallyToggled) {
      this.showThoughts.set(true);
    }
  }

  toggleThoughts() {
    this.manuallyToggled = true;
    this.showThoughts.update(v => !v);
  }

  onCitationClick(citation: Citation): void {
    this.chatService.setSelectedChunk(citation.chunkId);
    this.uiState.openEvidence(); // Open the evidence panel
  }

  async copyContent(): Promise<void> {
    try {
      await navigator.clipboard.writeText(this.message.content);
      this.copied = true;
      setTimeout(() => (this.copied = false), 2000);
    } catch {
      // fallback silent fail
    }
  }
}
