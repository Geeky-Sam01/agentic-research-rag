import { Component } from '@angular/core';
import { AppShellComponent } from './components/app-shell/app-shell.component';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [AppShellComponent],
  template: `<app-shell />`
})
export class App {}
