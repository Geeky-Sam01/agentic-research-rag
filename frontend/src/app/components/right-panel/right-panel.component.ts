import { Component, inject } from '@angular/core';
import { ChatService } from '../../services/chat.service';
import { ChunkItemComponent } from '../chunk-item/chunk-item.component';
import { Skeleton } from 'primeng/skeleton';

@Component({
  selector: 'app-right-panel',
  standalone: true,
  imports: [ChunkItemComponent, Skeleton],
  templateUrl: './right-panel.component.html',
  styleUrl: './right-panel.component.css',
  host: { 'class': 'flex-1 flex flex-col h-full min-h-0' }
})
export class RightPanelComponent {
  chatService = inject(ChatService);
}
