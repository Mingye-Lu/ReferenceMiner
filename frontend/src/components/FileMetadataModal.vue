<script setup lang="ts">
import { ref, watch } from "vue"
import BaseModal from "./BaseModal.vue"
import type { ManifestEntry, BibliographyAuthor } from "../types"
import { extractFileMetadata, fetchFileMetadata, updateFileMetadata } from "../api/client"
import { getFileName } from "../utils"

const props = defineProps<{
  modelValue: boolean
  file: ManifestEntry | null
}>()

const emit = defineEmits<{
  (event: "update:modelValue", value: boolean): void
}>()

type BibliographyDraft = NonNullable<ManifestEntry["bibliography"]>

const isLoading = ref(false)
const isSaving = ref(false)
const isExtracting = ref(false)
const errorMessage = ref("")
const draft = ref<BibliographyDraft>(emptyDraft())

const docTypeOptions = [
  { value: "J", label: "Journal Article [J]" },
  { value: "C", label: "Conference Paper [C]" },
  { value: "M", label: "Book/Monograph [M]" },
  { value: "D", label: "Thesis [D]" },
  { value: "R", label: "Report [R]" },
  { value: "S", label: "Standard [S]" },
  { value: "P", label: "Patent [P]" },
  { value: "N", label: "Newspaper [N]" },
  { value: "EB", label: "Online Resource [EB]" },
  { value: "Z", label: "Other [Z]" },
]

const languageOptions = [
  { value: "zh", label: "Chinese" },
  { value: "en", label: "English" },
  { value: "other", label: "Other" },
]

function emptyDraft(): BibliographyDraft {
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
  }
}

function normalizeDraft(input: ManifestEntry["bibliography"] | null): BibliographyDraft {
  const base = emptyDraft()
  if (!input) return base
  return {
    ...base,
    ...input,
    authors: (input.authors ?? []).map((author) => ({
      family: author.family ?? "",
      given: author.given ?? "",
      literal: author.literal ?? "",
      sequence: author.sequence ?? null,
    })),
  }
}

async function loadMetadata() {
  if (!props.file) {
    draft.value = emptyDraft()
    return
  }
  isLoading.value = true
  errorMessage.value = ""
  try {
    const remote = await fetchFileMetadata(props.file.relPath)
    draft.value = normalizeDraft(remote || props.file.bibliography || null)
  } catch (error: any) {
    draft.value = normalizeDraft(props.file.bibliography || null)
    errorMessage.value = error?.message || "Failed to load metadata."
  } finally {
    isLoading.value = false
  }
}

function cleanText(value: string | null | undefined): string | null {
  const trimmed = (value ?? "").trim()
  return trimmed ? trimmed : null
}

function sanitizeAuthors(authors: BibliographyAuthor[] | undefined): BibliographyAuthor[] {
  if (!authors) return []
  return authors
    .map((author) => ({
      family: cleanText(author.family ?? null),
      given: cleanText(author.given ?? null),
      literal: cleanText(author.literal ?? null),
      sequence: author.sequence ?? null,
    }))
    .filter((author) => author.family || author.given || author.literal)
}

function buildPayload() {
  const current = draft.value
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
  }
}

function addAuthor() {
  draft.value.authors = [...(draft.value.authors ?? []), { family: "", given: "", literal: "" }]
}

function removeAuthor(index: number) {
  if (!draft.value.authors) return
  draft.value.authors = draft.value.authors.filter((_, i) => i !== index)
}

async function handleSave() {
  if (!props.file) return
  isSaving.value = true
  errorMessage.value = ""
  try {
    const payload = buildPayload()
    const updated = await updateFileMetadata(props.file.relPath, payload)
    draft.value = normalizeDraft(updated)
    emit("update:modelValue", false)
  } catch (error: any) {
    errorMessage.value = error?.message || "Failed to save metadata."
  } finally {
    isSaving.value = false
  }
}

async function handleExtract() {
  if (!props.file) return
  isExtracting.value = true
  errorMessage.value = ""
  try {
    // Use force=true to replace existing metadata with fresh extraction
    const updated = await extractFileMetadata(props.file.relPath, true)
    draft.value = normalizeDraft(updated)
  } catch (error: any) {
    errorMessage.value = error?.message || "Failed to extract metadata."
  } finally {
    isExtracting.value = false
  }
}

function handleClose() {
  emit("update:modelValue", false)
}

watch(
  () => props.modelValue,
  (isOpen) => {
    if (isOpen) {
      loadMetadata()
    }
  }
)
</script>

<template>
  <BaseModal :model-value="modelValue" :title="file ? `${getFileName(file.relPath)} Metadata` : 'Metadata'" size="large"
    @update:model-value="handleClose">
    <div class="metadata-modal">
      <div v-if="isLoading" class="metadata-loading">Loading metadata...</div>
      <div v-else-if="!file" class="metadata-empty">Select a file to edit metadata.</div>
      <div v-else class="metadata-form">
        <div class="metadata-row">
          <label>Document Type</label>
          <select v-model="draft!.docType">
            <option value="">Select type</option>
            <option v-for="opt in docTypeOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
          </select>
        </div>
        <div class="metadata-row">
          <label>Language</label>
          <select v-model="draft!.language">
            <option value="">Select language</option>
            <option v-for="opt in languageOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
          </select>
        </div>
        <div class="metadata-row">
          <label>Title</label>
          <input v-model="draft!.title" type="text" placeholder="Paper title" />
        </div>
        <div class="metadata-row">
          <label>Subtitle</label>
          <input v-model="draft!.subtitle" type="text" placeholder="Subtitle (optional)" />
        </div>
        <div class="metadata-row">
          <label>Organization</label>
          <input v-model="draft!.organization" type="text" placeholder="Institution or group author" />
        </div>

        <div class="metadata-row">
          <label>Authors</label>
          <div class="authors-list">
            <div v-for="(author, index) in draft!.authors" :key="index" class="author-row">
              <input v-model="author.family" type="text" placeholder="Family name" />
              <input v-model="author.given" type="text" placeholder="Given name" />
              <input v-model="author.literal" type="text" placeholder="Full name (optional)" />
              <button class="btn-remove" @click="removeAuthor(index)">Remove</button>
            </div>
            <button class="btn-secondary" @click="addAuthor">Add author</button>
          </div>
        </div>

        <div class="metadata-grid">
          <div class="metadata-row">
            <label>Year</label>
            <input v-model.number="draft!.year" type="number" placeholder="2024" />
          </div>
          <div class="metadata-row">
            <label>Date</label>
            <input v-model="draft!.date" type="text" placeholder="YYYY-MM-DD" />
          </div>
          <div class="metadata-row">
            <label>Journal</label>
            <input v-model="draft!.journal" type="text" placeholder="Journal name" />
          </div>
          <div class="metadata-row">
            <label>Volume</label>
            <input v-model="draft!.volume" type="text" placeholder="Volume" />
          </div>
          <div class="metadata-row">
            <label>Issue</label>
            <input v-model="draft!.issue" type="text" placeholder="Issue" />
          </div>
          <div class="metadata-row">
            <label>Pages</label>
            <input v-model="draft!.pages" type="text" placeholder="123-130" />
          </div>
          <div class="metadata-row">
            <label>Publisher</label>
            <input v-model="draft!.publisher" type="text" placeholder="Publisher" />
          </div>
          <div class="metadata-row">
            <label>Place</label>
            <input v-model="draft!.place" type="text" placeholder="City" />
          </div>
          <div class="metadata-row">
            <label>Conference</label>
            <input v-model="draft!.conference" type="text" placeholder="Conference name" />
          </div>
          <div class="metadata-row">
            <label>Institution</label>
            <input v-model="draft!.institution" type="text" placeholder="University or institute" />
          </div>
          <div class="metadata-row">
            <label>Report Number</label>
            <input v-model="draft!.reportNumber" type="text" placeholder="Report number" />
          </div>
          <div class="metadata-row">
            <label>Standard Number</label>
            <input v-model="draft!.standardNumber" type="text" placeholder="Standard number" />
          </div>
          <div class="metadata-row">
            <label>Patent Number</label>
            <input v-model="draft!.patentNumber" type="text" placeholder="Patent number" />
          </div>
        </div>

        <div class="metadata-row">
          <label>URL</label>
          <input v-model="draft!.url" type="text" placeholder="https://..." />
        </div>
        <div class="metadata-row">
          <label>Accessed</label>
          <input v-model="draft!.accessed" type="text" placeholder="YYYY-MM-DD" />
        </div>
        <div class="metadata-row">
          <label>DOI</label>
          <input v-model="draft!.doi" type="text" placeholder="10.xxxx/xxxxx" />
        </div>
        <div class="metadata-row">
          <label>DOI Status</label>
          <input v-model="draft!.doiStatus" type="text" placeholder="missing/verified" />
        </div>

        <div v-if="errorMessage" class="metadata-error">{{ errorMessage }}</div>

        <div class="metadata-actions">
          <button class="btn-secondary" @click="handleClose">Cancel</button>
          <button class="btn-secondary" :disabled="isExtracting" @click="handleExtract">
            {{ isExtracting ? "Extracting..." : "Extract Metadata" }}
          </button>
          <button class="btn-primary" :disabled="isSaving" @click="handleSave">
            {{ isSaving ? "Saving..." : "Save Metadata" }}
          </button>
        </div>
      </div>
    </div>
  </BaseModal>
</template>

<style scoped>
.metadata-modal {
  display: flex;
  flex-direction: column;
  gap: 16px;
  color: var(--text-primary);
}

.metadata-loading,
.metadata-empty {
  padding: 20px;
  text-align: center;
  color: var(--text-secondary);
}

.metadata-form {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.metadata-row {
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 13px;
}

.metadata-row label {
  font-weight: 600;
  color: var(--text-secondary);
}

.metadata-row input,
.metadata-row select {
  padding: 8px 10px;
  border-radius: 8px;
  border: 1px solid var(--border-color);
  background: var(--bg-card);
  color: var(--text-primary);
  font-size: 13px;
}

.metadata-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 12px;
}

.authors-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.author-row {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr auto;
  gap: 8px;
  align-items: center;
}

.btn-secondary,
.btn-primary,
.btn-remove {
  border: none;
  border-radius: 8px;
  padding: 8px 12px;
  font-size: 12px;
  cursor: pointer;
}

.btn-secondary {
  background: var(--color-neutral-120);
  color: var(--text-primary);
}

.btn-primary {
  background: var(--accent-color);
  color: white;
}

.btn-remove {
  background: transparent;
  color: var(--color-danger-500);
}

.metadata-error {
  color: var(--color-danger-500);
  font-size: 12px;
}

.metadata-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  padding-top: 8px;
}
</style>
