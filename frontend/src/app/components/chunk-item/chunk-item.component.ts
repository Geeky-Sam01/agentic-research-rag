import { Component, Input } from '@angular/core';
import { Chunk } from '../../models/chat.models';
import { CardModule } from 'primeng/card';

import { CommonModule, DecimalPipe } from '@angular/common';

@Component({
  selector: 'app-chunk-item',
  standalone: true,
  imports: [CommonModule, CardModule ], //DecimalPipe
  templateUrl: './chunk-item.component.html'
})
export class ChunkItemComponent {
  @Input({ required: true }) chunk!: Chunk;
  @Input() isSelected = false;

  shortSourceId(): string {
    const parts = this.chunk.sourceId.replace(/\\/g, '/').split('/');
    return parts[parts.length - 1] || this.chunk.sourceId;
  }
}
