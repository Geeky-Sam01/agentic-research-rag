import { Component, Input } from '@angular/core';

@Component({
  selector: 'app-source-item',
  standalone: true,
  imports: [],
  templateUrl: './source-item.component.html'
})
export class SourceItemComponent {
  @Input({ required: true }) name!: string;

  shortName(): string {
    // Strip path, keep filename
    const parts = this.name.replace(/\\/g, '/').split('/');
    return parts[parts.length - 1] || this.name;
  }
}
