<script setup lang="ts">
import { computed, ref, watch } from "vue";
import CustomSelect from "./CustomSelect.vue";
import type { Bibliography, BibliographyAuthor } from "../types";

const props = withDefaults(
  defineProps<{
    modelValue: Bibliography | null;
    file: File;
    compact?: boolean;
  }>(),
  {
    compact: false,
  },
);

const emit = defineEmits<{
  (event: "update:modelValue", value: Bibliography | null): void;
  (event: "save"): void;
}>();

const showAdvanced = ref(false);
const draft = ref<Bibliography>(emptyDraft());

const docType = computed(() => draft.value?.docType ?? "");
const isJournal = computed(() => docType.value === "J");
const isConference = computed(() => docType.value === "C");
const isBook = computed(() => docType.value === "M");
const isThesis = computed(() => docType.value === "D");
const isReport = computed(() => docType.value === "R");
const isStandard = computed(() => docType.value === "S");
const isPatent = computed(() => docType.value === "P");
const isOnline = computed(() => docType.value === "EB");
const isOther = computed(() => !docType.value || docType.value === "Z");

const docTypeOptions = [
  { value: "J", label: "Journal [J]" },
  { value: "C", label: "Conference [C]" },
  { value: "M", label: "Book [[M]" },
  { value: "D", label: "Thesis [D]" },
  { value: "R", label: "Report [R]" },
  { value: "S", label: "Standard [S]" },
  { value: "P", label: "Patent [P]" },
  { value: "N", label: "Newspaper [N]" },
  { value: "EB", label: "Online [EB]" },
  { value: "Z", label: "Other [Z]" },
];

const languageOptions = [
  { value: "zh", label: "Chinese" },
  { value: "en", label: "English" },
  { value: "other", label: "Other" },
];

function emptyDraft(): Bibliography {
  return {
    docType: null,
    language: null,
    title: null,
    subtitle: null,
    authors: [],
    organization: null,
    year: null,
    date: null,
    journal: null,
    volume: null,
    issue: null,
    pages: null,
    publisher: null,
    place: null,
    conference: null,
    institution: null,
    reportNumber: null,
    standardNumber: null,
    patentNumber: null,
    url: null,
    accessed: null,
    doi: null,
    doiStatus: null,
    extraction: null,
    verification: null,
  };
}

function normalizeDraft(input: Bibliography | null): Bibliography {
  const base = emptyDraft();
  if (!input) return base;
  return {
    ...base,
    ...input,
    authors: (input.authors ?? []).map((author) => ({
      family: author.family ?? "",
      given: author.given ?? "",
      literal: author.literal ?? "",
      sequence: author.sequence ?? null,
    })),
  };
}

function cleanText(value: string | null | undefined): string | null {
  const trimmed = (value ?? "").trim();
  return trimmed ? trimmed : null;
}

function sanitizeAuthors(
  authors: BibliographyAuthor[] | undefined,
): BibliographyAuthor[] {
  if (!authors) return [];
  return authors
    .map((author) => ({
      family: cleanText(author.family ?? null),
      given: cleanText(author.given ?? null),
      literal: cleanText(author.literal ?? null),
      sequence: author.sequence ?? null,
    }))
    .filter((author) => author.family || author.given || author.literal);
}

function buildPayload(): Bibliography {
  const current = draft.value;
  return {
    docType: cleanText(current.docType ?? null),
    language: cleanText(current.language ?? null),
    title: cleanText(current.title ?? null),
    subtitle: cleanText(current.subtitle ?? null),
    authors: sanitizeAuthors(current.authors),
    organization: cleanText(current.organization ?? null),
    year: current.year ?? null,
    date: cleanText(current.date ?? null),
    journal: cleanText(current.journal ?? null),
    volume: cleanText(current.volume ?? null),
    issue: cleanText(current.issue ?? null),
    pages: cleanText(current.pages ?? null),
    publisher: cleanText(current.publisher ?? null),
    place: cleanText(current.place ?? null),
    conference: cleanText(current.conference ?? null),
    institution: cleanText(current.institution ?? null),
    reportNumber: cleanText(current.reportNumber ?? null),
    standardNumber: cleanText(current.standardNumber ?? null),
    patentNumber: cleanText(current.patentNumber ?? null),
    url: cleanText(current.url ?? null),
    accessed: cleanText(current.accessed ?? null),
    doi: cleanText(current.doi ?? null),
    doiStatus: cleanText(current.doiStatus ?? null),
    extraction: current.extraction ?? null,
    verification: current.verification ?? null,
  };
}

function addAuthor() {
  draft.value.authors = [
    ...(draft.value.authors ?? []),
    { family: "", given: "", literal: "" },
  ];
}

function removeAuthor(index: number) {
  if (!draft.value.authors) return;
  draft.value.authors = draft.value.authors.filter((_, i) => i !== index);
}

function handleSave() {
  const payload = buildPayload();
  emit("update:modelValue", payload);
  emit("save");
}

watch(
  () => props.modelValue,
  (value) => {
    draft.value = normalizeDraft(value);
  },
  { immediate: true },
);

watch(
  draft,
  () => {
    emit("update:modelValue", buildPayload());
  },
  { deep: true },
);
</script>

<template>
  <div class="bibliography-editor" :class="{ compact }">
    <div class="editor-header">
      <span class="file-name">{{ file.name }}</span>
    </div>

    <div class="form-section">
      <div class="section-title">Core</div>
      <div class="form-row">
        <label class="form-label">Document Type</label>
        <CustomSelect
          :model-value="draft!.docType ?? ''"
          :options="docTypeOptions"
          @update:model-value="(value: string) => (draft!.docType = value)"
          placeholder="Select type"
        />
      </div>
      <div class="form-row">
        <label class="form-label">Title</label>
        <input
          v-model="draft!.title"
          type="text"
          placeholder="Paper title"
          class="form-input"
        />
      </div>

      <div class="form-row">
        <label class="form-label">Authors</label>
        <div class="authors-list">
          <div
            v-for="(author, index) in draft!.authors"
            :key="index"
            class="author-row"
          >
            <input
              v-model="author.family"
              type="text"
              placeholder="Family name"
              class="form-input"
            />
            <input
              v-model="author.given"
              type="text"
              placeholder="Given name"
              class="form-input"
            />
            <input
              v-model="author.literal"
              type="text"
              placeholder="Full name (optional)"
              class="form-input"
            />
            <button class="btn-danger" @click="removeAuthor(index)">
              Remove
            </button>
          </div>
          <button class="btn-primary" @click="addAuthor">Add author</button>
        </div>
      </div>
      <div class="form-row">
        <label class="form-label">Year</label>
        <input
          v-model.number="draft!.year"
          type="number"
          placeholder="2024"
          class="form-input"
        />
      </div>
    </div>

    <div v-if="isJournal" class="form-section">
      <div class="section-title">Journal</div>
      <div class="form-grid">
        <div class="form-row">
          <label class="form-label">Journal</label>
          <input
            v-model="draft!.journal"
            type="text"
            placeholder="Journal name"
            class="form-input"
          />
        </div>
        <div class="form-row">
          <label class="form-label">Volume</label>
          <input
            v-model="draft!.volume"
            type="text"
            placeholder="Volume"
            class="form-input"
          />
        </div>
        <div class="form-row">
          <label class="form-label">Issue</label>
          <input
            v-model="draft!.issue"
            type="text"
            placeholder="Issue"
            class="form-input"
          />
        </div>
        <div class="form-row">
          <label class="form-label">Pages</label>
          <input
            v-model="draft!.pages"
            type="text"
            placeholder="123-130"
            class="form-input"
          />
        </div>
      </div>
    </div>

    <div v-if="isConference" class="form-section">
      <div class="section-title">Conference</div>
      <div class="form-grid">
        <div class="form-row">
          <label class="form-label">Conference</label>
          <input
            v-model="draft!.conference"
            type="text"
            placeholder="Conference name"
            class="form-input"
          />
        </div>
        <div class="form-row">
          <label class="form-label">Pages</label>
          <input
            v-model="draft!.pages"
            type="text"
            placeholder="123-130"
            class="form-input"
          />
        </div>
      </div>
    </div>

    <div v-if="isBook" class="form-section">
      <div class="section-title">Book</div>
      <div class="form-grid">
        <div class="form-row">
          <label class="form-label">Publisher</label>
          <input
            v-model="draft!.publisher"
            type="text"
            placeholder="Publisher"
            class="form-input"
          />
        </div>
        <div class="form-row">
          <label class="form-label">Place</label>
          <input
            v-model="draft!.place"
            type="text"
            placeholder="City"
            class="form-input"
          />
        </div>
        <div class="form-row">
          <label class="form-label">Pages</label>
          <input
            v-model="draft!.pages"
            type="text"
            placeholder="123-130"
            class="form-input"
          />
        </div>
      </div>
    </div>

    <div v-if="isThesis" class="form-section">
      <div class="section-title">Thesis</div>
      <div class="form-grid">
        <div class="form-row">
          <label class="form-label">Institution</label>
          <input
            v-model="draft!.institution"
            type="text"
            placeholder="University or institute"
            class="form-input"
          />
        </div>
        <div class="form-row">
          <label class="form-label">Place</label>
          <input
            v-model="draft!.place"
            type="text"
            placeholder="City"
            class="form-input"
          />
        </div>
      </div>
    </div>

    <div v-if="isReport" class="form-section">
      <div class="section-title">Report</div>
      <div class="form-grid">
        <div class="form-row">
          <label class="form-label">Report Number</label>
          <input
            v-model="draft!.reportNumber"
            type="text"
            placeholder="Report number"
            class="form-input"
          />
        </div>
        <div class="form-row">
          <label class="form-label">Institution</label>
          <input
            v-model="draft!.institution"
            type="text"
            placeholder="University or institute"
            class="form-input"
          />
        </div>
        <div class="form-row">
          <label class="form-label">Publisher</label>
          <input
            v-model="draft!.publisher"
            type="text"
            placeholder="Publisher"
            class="form-input"
          />
        </div>
      </div>
    </div>

    <div v-if="isStandard" class="form-section">
      <div class="section-title">Standard</div>
      <div class="form-row">
        <label class="form-label">Standard Number</label>
        <input
          v-model="draft!.standardNumber"
          type="text"
          placeholder="Standard number"
          class="form-input"
        />
      </div>
    </div>

    <div v-if="isPatent" class="form-section">
      <div class="section-title">Patent</div>
      <div class="form-row">
        <label class="form-label">Patent Number</label>
        <input
          v-model="draft!.patentNumber"
          type="text"
          placeholder="Patent number"
          class="form-input"
        />
      </div>
    </div>

    <div v-if="isOnline" class="form-section">
      <div class="section-title">Online</div>
      <div class="form-row">
        <label class="form-label">Accessed</label>
        <input
          v-model="draft!.accessed"
          type="text"
          placeholder="YYYY-MM-DD"
          class="form-input"
        />
      </div>
    </div>

    <div v-if="isOther" class="form-section">
      <div class="section-title">General Details</div>
      <div class="form-grid">
        <div class="form-row">
          <label class="form-label">Journal</label>
          <input
            v-model="draft!.journal"
            type="text"
            placeholder="Journal name"
            class="form-input"
          />
        </div>
        <div class="form-row">
          <label class="form-label">Conference</label>
          <input
            v-model="draft!.conference"
            type="text"
            placeholder="Conference name"
            class="form-input"
          />
        </div>
        <div class="form-row">
          <label class="form-label">Publisher</label>
          <input
            v-model="draft!.publisher"
            type="text"
            placeholder="Publisher"
            class="form-input"
          />
        </div>
        <div class="form-row">
          <label class="form-label">Place</label>
          <input
            v-model="draft!.place"
            type="text"
            placeholder="City"
            class="form-input"
          />
        </div>
        <div class="form-row">
          <label class="form-label">Pages</label>
          <input
            v-model="draft!.pages"
            type="text"
            placeholder="123-130"
            class="form-input"
          />
        </div>
      </div>
    </div>

    <div class="form-section">
      <div class="section-title">Links</div>
      <div class="form-grid">
        <div class="form-row">
          <label class="form-label">URL</label>
          <input
            v-model="draft!.url"
            type="text"
            placeholder="https://..."
            class="form-input"
          />
        </div>
        <div class="form-row">
          <label class="form-label">DOI</label>
          <input
            v-model="draft!.doi"
            type="text"
            placeholder="10.xxxx/xxxxx"
            class="form-input"
          />
        </div>
      </div>
    </div>

    <button
      class="metadata-advanced-toggle"
      type="button"
      @click="showAdvanced = !showAdvanced"
    >
      {{ showAdvanced ? "Hide advanced fields" : "Show advanced fields" }}
    </button>

    <div v-if="showAdvanced" class="form-section">
      <div class="section-title">Advanced</div>
      <div class="form-grid">
        <div class="form-row">
          <label class="form-label">Language</label>
          <CustomSelect
            :model-value="draft!.language ?? ''"
            :options="languageOptions"
            @update:model-value="(value: string) => (draft!.language = value)"
            placeholder="Select language"
          />
        </div>
        <div class="form-row">
          <label class="form-label">Subtitle</label>
          <input
            v-model="draft!.subtitle"
            type="text"
            placeholder="Subtitle (optional)"
            class="form-input"
          />
        </div>
        <div class="form-row">
          <label class="form-label">Date</label>
          <input
            v-model="draft!.date"
            type="text"
            placeholder="YYYY-MM-DD"
            class="form-input"
          />
        </div>
        <div class="form-row">
          <label class="form-label">Organization</label>
          <input
            v-model="draft!.organization"
            type="text"
            placeholder="Institution or group author"
            class="form-input"
          />
        </div>
        <div class="form-row">
          <label class="form-label">DOI Status</label>
          <input
            v-model="draft!.doiStatus"
            type="text"
            placeholder="missing/verified"
            class="form-input"
          />
        </div>
        <div class="form-row" v-if="!isOnline">
          <label class="form-label">Accessed</label>
          <input
            v-model="draft!.accessed"
            type="text"
            placeholder="YYYY-MM-DD"
            class="form-input"
          />
        </div>
      </div>
    </div>

    <div class="editor-footer">
      <button class="btn-primary" @click="handleSave">Save</button>
    </div>
  </div>
</template>

<style scoped>
.bibliography-editor {
  display: flex;
  flex-direction: column;
  gap: 12px;
  color: var(--text-primary);
  height: 100%;
}

.bibliography-editor.compact {
  gap: 8px;
}

.editor-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--border-card);
}

.file-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
}

.section-title {
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--text-secondary);
  margin-top: 4px;
}

.form-section {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.bibliography-editor.compact .form-section {
  gap: 8px;
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 8px;
}

.metadata-advanced-toggle {
  align-self: flex-start;
  border: 1px solid var(--border-card);
  background: var(--bg-card);
  color: var(--text-primary);
  font-size: 11px;
  padding: 5px 8px;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.15s;
}

.metadata-advanced-toggle:hover {
  border-color: var(--accent-bright);
  color: var(--accent-bright);
}

.authors-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.author-row {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr auto;
  gap: 6px;
  align-items: center;
}

.editor-footer {
  margin-top: auto;
  padding-top: 12px;
  border-top: 1px solid var(--border-card);
  display: flex;
  justify-content: flex-end;
}
</style>
