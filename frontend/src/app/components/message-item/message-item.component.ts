import { Component, Input, inject } from '@angular/core';
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
export class MessageItemComponent {
  @Input({ required: true }) message!: Message;

  chatService = inject(ChatService);
  uiState = inject(UiStateService);
  copied = false;

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
