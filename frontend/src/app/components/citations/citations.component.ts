import { Component, Input, Output, EventEmitter } from '@angular/core';
import { Citation } from '../../models/chat.models';

import { Chip } from 'primeng/chip';

@Component({
  selector: 'app-citations',
  standalone: true,
  imports: [Chip],
  templateUrl: './citations.component.html'
})
export class CitationsComponent {
  @Input() citations: Citation[] = [];
  @Output() open = new EventEmitter<Citation>();
}
