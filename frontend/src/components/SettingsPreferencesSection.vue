<script setup lang="ts">
import type { Theme } from "../utils/theme";
import { ArrowUpRight, FileText, Monitor, Sun } from "lucide-vue-next";
import CustomSelect from "./CustomSelect.vue";

interface ThemeOption {
  value: string;
  label: string;
}

interface PdfViewOption {
  value: string;
  label: string;
}

interface CitationFormatOption {
  value: string;
  label: string;
}

const props = defineProps<{
  currentTheme: Theme;
  themeOptions: ThemeOption[];
  onThemeChange: (value: Theme) => void;
  viewMode: "single" | "continuous";
  pdfViewOptions: PdfViewOption[];
  onViewModeChange: (value: "single" | "continuous") => void;
  citationCopyFormat: string;
  citationFormatOptions: CitationFormatOption[];
  isSavingCitation: boolean;
  onCitationFormatChange: (value: string) => void;
  filesPerPage: number;
  notesPerPage: number;
  chatsPerPage: number;
  onDisplaySettingChange: (
    key: "filesPerPage" | "notesPerPage" | "chatsPerPage",
    value: number,
  ) => void;
}>();

const emitDisplayChange = (
  key: "filesPerPage" | "notesPerPage" | "chatsPerPage",
  event: Event,
) => {
  const target = event.target as HTMLInputElement;
  const value = parseInt(target.value, 10) || 0;
  props.onDisplaySettingChange(key, value);
};
</script>

<template>
  <div class="settings-section-container">
    <div class="settings-header">
      <h2 class="settings-section-title">Preferences</h2>
      <p class="settings-section-desc">
        Customize your experience with theme, keyboard shortcuts, and display
        options.
      </p>
    </div>

    <div class="start-settings-content">
      <!-- Theme Card -->
      <section class="settings-card">
        <div class="section-header">
          <div class="section-icon">
            <Sun :size="16" />
          </div>
          <div>
            <h4 class="section-title">Theme</h4>
            <p class="section-description">Choose your preferred color theme</p>
          </div>
        </div>
        <div class="section-content">
          <div class="setting-row">
            <div class="setting-info">
              <label class="setting-label">Appearance</label>
              <p class="setting-hint">
                Select light, dark, or match your system settings
              </p>
            </div>
            <div class="setting-control setting-control--md">
              <CustomSelect
                :model-value="currentTheme"
                :options="themeOptions"
                @update:model-value="(value) => onThemeChange(value as Theme)"
              />
            </div>
          </div>
        </div>
      </section>

      <!-- PDF View Mode -->
      <section class="settings-card">
        <div class="section-header">
          <div class="section-icon">
            <FileText :size="16" />
          </div>
          <div>
            <h4 class="section-title">PDF Viewing</h4>
            <p class="section-description">Customize how you read documents</p>
          </div>
        </div>
        <div class="section-content">
          <div class="setting-row">
            <div class="setting-info">
              <label class="setting-label">Default View Mode</label>
              <p class="setting-hint">
                Choose between single page or continuous scrolling
              </p>
            </div>
            <div class="setting-control setting-control--md">
              <CustomSelect
                :model-value="viewMode"
                :options="pdfViewOptions"
                @update:model-value="
                  (value) => onViewModeChange(value as 'single' | 'continuous')
                "
              />
            </div>
          </div>
        </div>
      </section>

      <!-- Citation Format Card -->
      <section class="settings-card">
        <div class="section-header">
          <div class="section-icon">
            <svg
              xmlns="http://www.w3.org/2000/svg"
              width="16"
              height="16"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
              stroke-linejoin="round"
            >
              <path
                d="M3 21c3 0 7-1 7-8V5c0-1.25-.756-2.017-2-2H4c-1.25 0-2 .75-2 1.972V11c0 1.25.75 2 2 2 1 0 1 0 1 1v1c0 1-1 2-2 2s-1 .008-1 1.031V21"
              />
              <path
                d="M15 21c3 0 7-1 7-8V5c0-1.25-.757-2.017-2-2h-4c-1.25 0-2 .75-2 1.972V11c0 1.25.75 2 2 2h.75c0 2.25.25 4-2.75 4v3"
              />
            </svg>
          </div>
          <div>
            <h4 class="section-title">Citation Format</h4>
            <p class="section-description">Format for copying citations</p>
          </div>
        </div>
        <div class="section-content">
          <div class="setting-row">
            <div class="setting-info">
              <label class="setting-label">In-Text Citation Style</label>
              <p class="setting-hint">
                Replaces [C1] markers when copying responses
              </p>
            </div>
            <div class="setting-control setting-control--lg">
              <CustomSelect
                :model-value="citationCopyFormat"
                :options="citationFormatOptions"
                :disabled="isSavingCitation"
                @update:model-value="onCitationFormatChange"
              />
            </div>
          </div>
        </div>
      </section>

      <!-- Submit Prompt Key Card -->
      <section class="settings-card">
        <div class="section-header">
          <div class="section-icon">
            <ArrowUpRight :size="16" />
          </div>
          <div>
            <h4 class="section-title">Submit Prompt Key</h4>
            <p class="section-description">Choose how to submit your prompts</p>
          </div>
        </div>
        <div class="section-content">
          <div class="setting-row">
            <div class="setting-info">
              <label class="setting-label">Send Message</label>
              <p class="setting-hint">
                Configure keyboard shortcut for sending messages
              </p>
            </div>
            <div class="setting-control setting-control--lg">
              <div class="radio-inline-group">
                <label class="radio-inline-option">
                  <input type="radio" name="submitKey" value="enter" checked />
                  <span>Enter</span>
                </label>
                <label class="radio-inline-option">
                  <input type="radio" name="submitKey" value="ctrl-enter" />
                  <span>Ctrl+Enter</span>
                </label>
              </div>
            </div>
          </div>
        </div>
      </section>

      <!-- Display Card -->
      <section class="settings-card">
        <div class="section-header">
          <div class="section-icon">
            <Monitor :size="16" />
          </div>
          <div>
            <h4 class="section-title">Display</h4>
            <p class="section-description">
              Customize how content is displayed
            </p>
          </div>
        </div>
        <div class="section-content">
          <!-- Files Limit -->
          <div class="setting-row">
            <div class="setting-info">
              <label class="setting-label">Project Files Limit</label>
              <p class="setting-hint">
                Items per page in sidebar (0 for unlimited)
              </p>
            </div>
            <div class="setting-control setting-control--sm">
              <input
                type="number"
                min="0"
                class="form-input"
                :value="filesPerPage"
                @input="(event) => emitDisplayChange('filesPerPage', event)"
              />
            </div>
          </div>

          <!-- Notes Limit -->
          <div class="setting-row">
            <div class="setting-info">
              <label class="setting-label">Pinned Notes Limit</label>
              <p class="setting-hint">
                Notes per page in sidebar (0 for unlimited)
              </p>
            </div>
            <div class="setting-control setting-control--sm">
              <input
                type="number"
                min="0"
                class="form-input"
                :value="notesPerPage"
                @input="(event) => emitDisplayChange('notesPerPage', event)"
              />
            </div>
          </div>

          <!-- Chats Limit -->
          <div class="setting-row">
            <div class="setting-info">
              <label class="setting-label">Chat List Limit</label>
              <p class="setting-hint">
                Chats per page in sidebar (0 for unlimited)
              </p>
            </div>
            <div class="setting-control setting-control--sm">
              <input
                type="number"
                min="0"
                class="form-input"
                :value="chatsPerPage"
                @input="(event) => emitDisplayChange('chatsPerPage', event)"
              />
            </div>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>
