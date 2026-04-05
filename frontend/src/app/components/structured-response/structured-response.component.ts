import { Component, Input } from '@angular/core';
import { CommonModule } from '@angular/common';

@Component({
  selector: 'app-structured-response',
  standalone: true,
  imports: [CommonModule],
  template: `
    @if (data) {
      @switch (data.type) {
        @case ('table') {
          <div class="my-4">
            @if (data.title) {
              <h4 class="text-sm font-bold text-text-primary mb-2 uppercase tracking-wide opacity-80">{{ data.title }}</h4>
            }
            <div class="overflow-x-auto border border-border rounded-xl">
              <table class="w-full text-sm text-left text-text-secondary">
                <thead class="text-xs text-text-primary uppercase bg-panel border-b border-border">
                  <tr>
                    @for (header of (data.headers || data.columns); track header) {
                      <th scope="col" class="px-5 py-3 border-r border-border last:border-0">{{header}}</th>
                    }
                  </tr>
                </thead>
                <tbody>
                  @for (row of data.rows; track row) {
                    <tr class="bg-bg-main border-b border-border last:border-0 hover:bg-panel transition-colors">
                      @for (cell of row; track cell) {
                        <td class="px-5 py-3.5 border-r border-border last:border-0">{{cell}}</td>
                      }
                    </tr>
                  }
                </tbody>
              </table>
            </div>
          </div>
        }
        @case ('cards') {
          <div class="my-4">
            @if (data.title) {
              <h4 class="text-sm font-bold text-text-primary mb-3 uppercase tracking-wide opacity-80">{{ data.title }}</h4>
            }
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
              @for (card of data.cards; track card.heading) {
                <div class="p-4 rounded-xl border border-border bg-panel flex flex-col gap-2 hover:border-accent/40 hover:shadow-lg hover:shadow-accent/5 transition-all">
                   <div class="flex justify-between items-start gap-2">
                     <h4 class="font-bold text-text-primary text-[14px] m-0 leading-tight">{{card.heading}}</h4>
                     @if (card.tag) {
                       <span class="text-[9px] uppercase font-bold tracking-widest text-accent border border-accent/20 bg-accent/10 px-1.5 py-0.5 rounded-sm whitespace-nowrap">{{card.tag}}</span>
                     }
                   </div>
                   <p class="text-[13px] text-text-secondary m-0 leading-relaxed">{{card.body}}</p>
                </div>
              }
            </div>
          </div>
        }
        @case ('summary') {
          <div class="my-4 p-5 rounded-2xl border border-accent/20 bg-accent/[0.02] shadow-inner shadow-accent/5 relative overflow-hidden">
             <!-- decorative blob -->
             <div class="absolute -top-10 -right-10 w-32 h-32 bg-accent opacity-5 blur-3xl rounded-full"></div>
             
             @if (data.headline || data.title) {
                <h3 class="text-[16px] font-bold text-text-primary mt-0 mb-4 flex items-center gap-2">
                  <i class="pi pi-align-left text-accent text-[12px]"></i>
                  {{data.headline || data.title}}
                </h3>
             }
             @if (data.key_points) {
               <ul class="space-y-2 mb-4 pl-1">
                 @for (point of data.key_points; track point) {
                   <li class="text-[13.5px] text-text-secondary flex items-start gap-2.5 leading-relaxed">
                      <span class="w-1.5 h-1.5 rounded-full bg-accent/60 mt-2 flex-shrink-0"></span>
                      <span>{{point}}</span>
                   </li>
                 }
               </ul>
             }
             @if (data.text) {
               <p class="text-[13.5px] text-text-secondary leading-relaxed mb-0">{{data.text}}</p>
             }
             @if (data.conclusion) {
               <div class="text-[13px] text-text-primary font-medium border-t border-border/50 pt-3 opacity-90 mt-2">
                 {{data.conclusion}}
               </div>
             }
          </div>
        }
        @case ('metric') {
          <div class="my-4">
            @if (data.title) {
              <h4 class="text-sm font-bold text-text-primary mb-3 uppercase tracking-wide opacity-80">{{ data.title }}</h4>
            }
            <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
              @for (item of data.data; track item.label) {
                <div class="p-4 rounded-xl border border-border bg-panel flex flex-col items-center justify-center text-center gap-1 hover:border-accent hover:shadow-lg hover:shadow-accent/5 transition-all">
                  <div class="text-[11px] uppercase tracking-wider text-text-muted font-semibold">{{item.label}}</div>
                  <div class="text-2xl font-bold text-text-primary flex items-baseline gap-1">
                    {{item.value}}
                    @if (item.unit) {
                      <span class="text-xs text-accent font-medium">{{item.unit}}</span>
                    }
                  </div>
                </div>
              }
            </div>
          </div>
        }
        @case ('finsight') {
          <div class="flex flex-col gap-2">
            @for (block of data.blocks; track $index) {
              <app-structured-response [data]="block" />
            }
          </div>
        }

        @case ('mixed') {
          <div class="flex flex-col gap-2">
            @for (block of data.blocks; track $index) {
              <app-structured-response [data]="block.content" />
            }
          </div>
        }
        @default {
           <!-- Fallback raw render -->
           <pre class="text-xs p-4 bg-panel border-border text-text-secondary overflow-x-auto">{{ data | json }}</pre>
        }
      }
    }
  `
})
export class StructuredResponseComponent {
  @Input() data: any | null = null;
}
