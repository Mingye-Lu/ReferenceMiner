<script setup lang="ts">
import { ref, computed, watch } from "vue";
import BaseModal from "./BaseModal.vue";
import { downloadPapersQueueStream, searchPapers, fetchMetadata } from "../api/client";
import { useQueue } from "../composables/useQueue";
import { ExternalLink, Download, Search, Check, AlertCircle, Loader2 } from "lucide-vue-next";
import type { CitationItem, CrawlerSearchResult } from "../types";

const props = defineProps<{
    modelValue: boolean;
    references: CitationItem[];
    sourceFileName?: string;
    isLoading?: boolean;
    expectedCount?: number;
}>();

const emit = defineEmits<{
    (e: "update:modelValue", value: boolean): void;
}>();

const { launchQueueEject } = useQueue();

const downloadQueueing = ref<Set<string>>(new Set());
const downloadQueued = ref<Set<string>>(new Set());
const downloadErrors = ref<Record<string, string>>({});
const searchingItems = ref<Set<string>>(new Set());
const searchResults = ref<Record<string, CrawlerSearchResult | null>>({});

// Selected items for batch download
const selectedItems = ref<Set<string>>(new Set());

function getCitationKey(item: CitationItem, index: number): string {
    return `ref-${item.ref_number || index}`;
}

// Stats computed
const stats = computed(() => {
    const downloadable = props.references.filter(r => r.availability === "downloadable").length;
    const linkOnly = props.references.filter(r => r.availability === "link_only").length;
    const searchable = props.references.filter(r => r.availability === "searchable").length;
    const unavailable = props.references.filter(r => r.availability === "unavailable").length;
    return { downloadable, linkOnly, searchable, unavailable, total: props.references.length };
});

const downloadableItems = computed(() =>
    props.references.filter(r => r.availability === "downloadable" || searchResults.value[getCitationKey(r, props.references.indexOf(r))])
);

const allDownloadableSelected = computed(() => {
    if (downloadableItems.value.length === 0) return false;
    return downloadableItems.value.every((item) =>
        selectedItems.value.has(getCitationKey(item, props.references.indexOf(item)))
    );
});

function toggleSelectAll() {
    if (allDownloadableSelected.value) {
        selectedItems.value.clear();
    } else {
        downloadableItems.value.forEach((item) => {
            const idx = props.references.indexOf(item);
            selectedItems.value.add(getCitationKey(item, idx));
        });
    }
}

function toggleSelect(key: string) {
    if (selectedItems.value.has(key)) {
        selectedItems.value.delete(key);
    } else {
        selectedItems.value.add(key);
    }
}

function formatAuthors(authors?: string[]): string {
    if (!authors || authors.length === 0) return "";
    if (authors.length <= 2) return authors.join(" & ");
    return `${authors[0]} et al.`;
}

async function queueDownload(item: CitationItem, index: number, event?: MouseEvent) {
    const key = getCitationKey(item, index);
    if (downloadQueueing.value.has(key) || downloadQueued.value.has(key)) return;

    // Build search result for download API
    let searchResult: CrawlerSearchResult;

    // Check if we have a search result for this item
    const found = searchResults.value[key];
    if (found) {
        searchResult = found;
    } else {
        searchResult = {
            title: item.title || "Unknown Title",
            url: item.url || null,
            pdf_url: (item.arxiv_id
                ? `https://arxiv.org/pdf/${item.arxiv_id}.pdf`
                : (item.url && item.url.endsWith('.pdf') ? item.url : null)) || null,
            source: item.source_type,
            doi: item.doi || null,
            authors: item.authors || [],
            abstract: item.raw_text,
            year: item.year || null,
            hash: "",
            citations: null
        };
    }

    const target = event?.currentTarget as HTMLElement | null;
    const rect = target?.getBoundingClientRect();
    const startX = rect ? rect.left + rect.width / 2 : null;
    const startY = rect ? rect.top + rect.height / 2 : null;

    downloadQueueing.value.add(key);
    downloadErrors.value = { ...downloadErrors.value, [key]: "" };

    try {
        await downloadPapersQueueStream([searchResult], false);
        downloadQueued.value.add(key);
        if (startX !== null && startY !== null) {
            launchQueueEject(startX, startY);
        }
    } catch (e) {
        const message = e instanceof Error ? e.message : "Download failed";
        downloadErrors.value = { ...downloadErrors.value, [key]: message };
    } finally {
        downloadQueueing.value.delete(key);
    }
}

async function searchForPaper(item: CitationItem, index: number) {
    const key = getCitationKey(item, index);
    if (searchingItems.value.has(key)) return;

    searchingItems.value.add(key);

    try {
        // Use title as search query, or arxiv_id if available
        let query = item.title || item.raw_text.substring(0, 100);

        // For arXiv items, search by arXiv ID for better results
        if (item.arxiv_id) {
            query = `arxiv:${item.arxiv_id}`;
        }

        const results = await searchPapers({ query, max_results: 3 });

        if (results && results.length > 0) {
            // Take the first result with a PDF
            const withPdf = results.find(r => r.pdf_url);
            searchResults.value = {
                ...searchResults.value,
                [key]: withPdf || results[0]
            };
        } else {
            searchResults.value = { ...searchResults.value, [key]: null };
        }
    } catch (e) {
        console.error("Search failed:", e);
        searchResults.value = { ...searchResults.value, [key]: null };
    } finally {
        searchingItems.value.delete(key);
    }
}

// State for tracking auto-fetch progress
const autoFetchInProgress = ref(false);
// State for fetched metadata (separate from search results)
const fetchedMetadata = ref<Record<string, {
    title?: string;
    authors?: string[];
    year?: number;
    source: string;
    pdf_url?: string;
    is_academic: boolean;
}>>({});

// Auto-fetch metadata for items that need it
async function autoFetchMetadata() {
    if (autoFetchInProgress.value) return;

    // Find items that need metadata fetch (have URL/arxiv/doi but missing author/year)
    const itemsToFetch = props.references.filter((item, index) => {
        const key = getCitationKey(item, index);
        // Skip if already fetched
        if (fetchedMetadata.value[key]) return false;
        if (searchingItems.value.has(key)) return false;

        // Check if needs fetch: has identifiers but missing metadata (Author OR Year OR Title)
        const hasUrl = item.url || item.arxiv_id || item.doi;
        const missingMetadata = (!item.authors || item.authors.length === 0) || !item.year || !item.title;

        return hasUrl && missingMetadata;
    });

    if (itemsToFetch.length === 0) return;

    autoFetchInProgress.value = true;

    // Mark all as searching immediately
    itemsToFetch.forEach((item, index) => {
        searchingItems.value.add(getCitationKey(item, index));
    });

    // Process items one by one
    for (const item of itemsToFetch) {
        const index = props.references.indexOf(item);
        const key = getCitationKey(item, index);


        try {
            // Determine the URL to fetch
            let url = item.url || "";
            if (item.arxiv_id && !url) {
                url = `https://arxiv.org/abs/${item.arxiv_id}`;
            }
            if (item.doi && !url) {
                url = `https://doi.org/${item.doi}`;
            }

            if (url) {
                const metadata = await fetchMetadata({
                    url,
                    arxiv_id: item.arxiv_id || undefined,
                    doi: item.doi || undefined,
                });

                fetchedMetadata.value = {
                    ...fetchedMetadata.value,
                    [key]: metadata
                };

                // If we got a PDF URL, also store in searchResults for download
                if (metadata.pdf_url && metadata.is_academic) {
                    searchResults.value = {
                        ...searchResults.value,
                        [key]: {
                            hash: `fetched-${key}`,
                            title: metadata.title || item.title || "",
                            authors: metadata.authors || [],
                            year: metadata.year || null,
                            pdf_url: metadata.pdf_url,
                            source: metadata.source,
                            doi: item.doi || null,
                            url: url || null,
                            abstract: null,
                            citations: null
                        }
                    };
                }
            }
        } catch (e) {
            console.error("Metadata fetch failed:", e);
            // Mark as fetched with empty data to avoid retrying
            fetchedMetadata.value = {
                ...fetchedMetadata.value,
                [key]: { source: "error", is_academic: false }
            };
        } finally {
            searchingItems.value.delete(key);
        }

        // Small delay between requests
        await new Promise(resolve => setTimeout(resolve, 300));
    }

    autoFetchInProgress.value = false;
}

// Watch for references changes and trigger auto-fetch
watch(() => props.references, (newRefs) => {
    if (newRefs && newRefs.length > 0 && !props.isLoading) {
        // Delay slightly to let UI render first
        setTimeout(autoFetchMetadata, 100);
    }
}, { immediate: true });

// Get enhanced item data (merged with fetched metadata)
function getEnhancedItem(item: CitationItem, index: number): CitationItem {
    const key = getCitationKey(item, index);
    const metadata = fetchedMetadata.value[key];

    // Start with a clone of the original item
    const enhanced = { ...item };

    // Merge fetched metadata if available
    if (metadata) {
        if (metadata.title) enhanced.title = metadata.title;
        if (metadata.authors && metadata.authors.length > 0) {
            enhanced.authors = metadata.authors;
        }
        if (metadata.year) enhanced.year = metadata.year;

        // If we got a valid response (academic or third-party), update availability
        if (metadata.source !== 'error') {
            if (enhanced.availability === 'unavailable') {
                enhanced.availability = 'link_only';
            }
        }
    }

    const missingMetadata = (!enhanced.authors || enhanced.authors.length === 0) || !enhanced.year;
    const hasLink = !!(enhanced.url || enhanced.doi || enhanced.arxiv_id);

    if (missingMetadata && !hasLink) {
        enhanced.availability = 'unavailable';
    }

    return enhanced;
}

// Computed property for enhanced references to simplify template
const enhancedReferences = computed(() => {
    return props.references.map((item, index) => getEnhancedItem(item, index));
});



async function batchDownload(event?: MouseEvent) {
    const selected = props.references.filter((item, i) =>
        selectedItems.value.has(getCitationKey(item, i))
    );

    const papersToDownload: CrawlerSearchResult[] = selected.map((item) => {
        const key = getCitationKey(item, props.references.indexOf(item));
        const found = searchResults.value[key];
        if (found) return found;

        return {
            title: item.title || "Unknown Title",
            url: item.url || null,
            pdf_url: (item.arxiv_id
                ? `https://arxiv.org/pdf/${item.arxiv_id}.pdf`
                : (item.url && item.url.endsWith('.pdf') ? item.url : null)) || null,
            source: item.source_type,
            doi: item.doi || null,
            authors: item.authors || [],
            abstract: item.raw_text,
            year: item.year || null,
            hash: "",
            citations: null
        };
    }).filter(p => p.pdf_url || p.doi || p.url);

    if (papersToDownload.length === 0) return;

    try {
        await downloadPapersQueueStream(papersToDownload, false);
        const target = event?.currentTarget as HTMLElement | null;
        const rect = target?.getBoundingClientRect();
        if (rect) {
            launchQueueEject(rect.left + rect.width / 2, rect.top + rect.height / 2);
        }
        // Mark all as queued
        selected.forEach((item) => {
            downloadQueued.value.add(getCitationKey(item, props.references.indexOf(item)));
        });
    } catch (e) {
        console.error("Batch download failed:", e);
    }
}

function isDownloadable(item: CitationItem): boolean {
    return item.availability === "downloadable";
}

function hasSearchResult(key: string): boolean {
    return !!searchResults.value[key]?.pdf_url;
}

function canBeSelected(item: CitationItem, index: number): boolean {
    const key = getCitationKey(item, index);
    if (item.availability === "downloadable") return true;
    if (searchResults.value[key]?.pdf_url) return true;
    if (searchResults.value[key]?.pdf_url) return true;
    return false;
}

function getAvailabilityBadge(item: CitationItem, index: number): { text: string; class: string } {
    const key = getCitationKey(item, index);

    if (item.availability === "searchable") {
        const result = searchResults.value[key];
        if (result?.pdf_url) {
            return { text: result.source || "Found", class: "badge-found" };
        }
        if (result === null) {
            return { text: "Not Found", class: "badge-notfound" };
        }
        return { text: "Search", class: "badge-search" };
    }

    switch (item.availability) {
        case "downloadable":
            if (item.arxiv_id) return { text: "arXiv", class: "badge-arxiv" };
            if (item.doi) return { text: "DOI", class: "badge-doi" };
            return { text: "PDF", class: "badge-pdf" };
        case "link_only":
            return { text: "Link", class: "badge-link" };
        default:
            return { text: "N/A", class: "badge-unavailable" };
    }
}

function getLink(item: CitationItem): string | null {
    if (item.doi) return `https://doi.org/${item.doi}`;
    if (item.arxiv_id) return `https://arxiv.org/abs/${item.arxiv_id}`;
    if (item.url) return item.url;
    return null;
}

const skeletonCount = computed(() => props.expectedCount || 10);
</script>

<template>
    <BaseModal :model-value="modelValue" @update:model-value="emit('update:modelValue', $event)" title="References"
        size="large">
        <div class="references-modal">
            <!-- Loading State with Skeleton -->
            <div v-if="isLoading" class="loading-state">
                <div class="results-header">
                    <div class="results-stats">
                        <div class="skeleton-text skeleton-shimmer" style="width: 150px; height: 20px;"></div>
                    </div>
                </div>
                <div class="references-list">
                    <div v-for="n in skeletonCount" :key="n" class="reference-card skeleton-card">
                        <div class="ref-number skeleton-shimmer"></div>
                        <div class="ref-content">
                            <div class="skeleton-text skeleton-shimmer" style="width: 60%; height: 16px;"></div>
                            <div class="skeleton-text skeleton-shimmer"
                                style="width: 40%; height: 14px; margin-top: 8px;">
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Empty State -->
            <div v-else-if="references.length === 0" class="empty-state">
                <AlertCircle :size="48" />
                <p>No structured references found in this document.</p>
            </div>

            <!-- Results -->
            <template v-else>
                <!-- Results Header -->
                <div class="results-header">
                    <div class="results-stats">
                        <span class="stat-total">{{ stats.total }} references</span>
                        <span v-if="stats.downloadable > 0" class="stat-item stat-downloadable">
                            {{ stats.downloadable }} downloadable
                        </span>
                        <span v-if="stats.linkOnly > 0" class="stat-item stat-link">
                            {{ stats.linkOnly }} with links
                        </span>
                        <span v-if="stats.searchable > 0" class="stat-item stat-search">
                            {{ stats.searchable }} searchable
                        </span>
                    </div>
                    <div class="results-actions">
                        <button v-if="downloadableItems.length > 0" class="select-all-btn" @click="toggleSelectAll">
                            {{ allDownloadableSelected ? 'Deselect All' : 'Select All' }}
                        </button>
                        <button v-if="selectedItems.size > 0" class="batch-download-btn" @click="batchDownload($event)">
                            <Download :size="14" />
                            Download {{ selectedItems.size }} Selected
                        </button>
                    </div>
                </div>

                <!-- Reference List -->
                <div class="references-list">
                    <div v-for="(item, index) in enhancedReferences" :key="getCitationKey(item, index)"
                        class="reference-card" :class="{
                            'is-unavailable': item.availability === 'unavailable' && !searchResults[getCitationKey(item, index)],
                            'is-selected': selectedItems.has(getCitationKey(item, index)),
                            'has-result': hasSearchResult(getCitationKey(item, index)),
                            'is-fetching': item.needs_metadata_fetch && searchingItems.has(getCitationKey(item, index)),
                            'is-selectable': canBeSelected(item, index)
                        }" @click="canBeSelected(item, index) ? toggleSelect(getCitationKey(item, index)) : undefined">
                        <!-- Reference Number -->
                        <div class="ref-number">
                            <span v-if="selectedItems.has(getCitationKey(item, index))" class="check-icon">
                                <Check :size="14" />
                            </span>
                            <Loader2 v-else-if="searchingItems.has(getCitationKey(item, index))" :size="14"
                                class="spin" />
                            <span v-else>[{{ item.ref_number || index + 1 }}]</span>
                        </div>

                        <!-- Content - use enhanced item for display - switch to skeleton if fetching -->
                        <div class="ref-content">
                            <template v-if="searchingItems.has(getCitationKey(item, index))">
                                <div class="skeleton-text skeleton-shimmer"
                                    style="width: 80%; height: 20px; margin-bottom: 6px;"></div>
                                <div class="skeleton-text skeleton-shimmer" style="width: 40%; height: 14px;"></div>
                            </template>
                            <template v-else>
                                <h4 class="ref-title">
                                    <span class="availability-badge" :class="getAvailabilityBadge(item, index).class">
                                        {{ getAvailabilityBadge(item, index).text }}
                                    </span>
                                    {{ item.title || item.raw_text.substring(0, 80) + '...' }}
                                </h4>
                                <div class="ref-meta">
                                    <span v-if="item.authors && item.authors!.length" class="ref-authors">
                                        {{ formatAuthors(item.authors!) }}
                                    </span>
                                    <span v-if="item.year" class="ref-year">{{ item.year }}</span>
                                </div>
                            </template>

                            <!-- Search Result Found -->
                            <div v-if="searchResults[getCitationKey(item, index)]?.pdf_url && !item.needs_metadata_fetch"
                                class="search-found">
                                <Check :size="12" />
                                Found via search: {{ searchResults[getCitationKey(item, index)]?.source }}
                            </div>
                        </div>

                        <!-- Actions -->
                        <div class="ref-actions" @click.stop>
                            <!-- Link Button -->
                            <a v-if="getLink(item)" :href="getLink(item)!" target="_blank" class="action-btn link-btn"
                                title="Open Link">
                                <ExternalLink :size="16" />
                            </a>

                            <!-- Search Button (for searchable items) -->
                            <button
                                v-if="item.availability === 'searchable' && !searchResults[getCitationKey(item, index)]"
                                class="action-btn search-btn"
                                :disabled="searchingItems.has(getCitationKey(item, index))"
                                @click="searchForPaper(item, index)" title="Search for this paper">
                                <span v-if="searchingItems.has(getCitationKey(item, index))" class="loader"></span>
                                <Search v-else :size="16" />
                            </button>

                            <!-- Download Button -->
                            <button v-if="isDownloadable(item) || hasSearchResult(getCitationKey(item, index))"
                                class="action-btn download-btn"
                                :disabled="downloadQueueing.has(getCitationKey(item, index)) || downloadQueued.has(getCitationKey(item, index))"
                                @click="queueDownload(item, index, $event)" title="Download Paper">
                                <span v-if="downloadQueueing.has(getCitationKey(item, index))" class="loader"></span>
                                <Check v-else-if="downloadQueued.has(getCitationKey(item, index))" :size="16" />
                                <Download v-else :size="16" />
                            </button>
                        </div>

                        <div v-if="downloadErrors[getCitationKey(item, index)]" class="error-msg">
                            {{ downloadErrors[getCitationKey(item, index)] }}
                        </div>
                    </div>
                </div>
            </template>
        </div>
    </BaseModal>
</template>

<style scoped>
.references-modal {
    padding: 20px;
    display: flex;
    flex-direction: column;
    gap: 16px;
    height: 70vh;
    max-height: 70vh;
    overflow: hidden;
}

/* Results Header */
.results-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 12px;
    padding: 12px 16px;
    background: var(--bg-card);
    border: 1px solid var(--border-color);
    border-radius: 10px;
    flex-shrink: 0;
}

.skeleton-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.results-stats {
    display: flex;
    align-items: center;
    gap: 12px;
    flex-wrap: wrap;
}

.stat-total {
    font-weight: 600;
    color: var(--text-primary);
}

.stat-item {
    height: 20px;
    font-size: 12px;
    padding: 2px 8px;
    border-radius: 12px;
    background: var(--bg-badge);
    color: var(--text-secondary);
}

.stat-downloadable {
    background: var(--color-success-100);
    color: var(--color-success-700);
}

[data-theme="dark"] .stat-downloadable {
    background: rgba(34, 197, 94, 0.15);
    color: var(--color-success-400);
}

.stat-link {
    background: var(--color-info-100);
    color: var(--color-info-700);
}

[data-theme="dark"] .stat-link {
    background: rgba(59, 130, 246, 0.15);
    color: var(--color-info-400);
}

.stat-search {
    background: var(--color-warning-100);
    color: var(--color-warning-700);
}

[data-theme="dark"] .stat-search {
    background: rgba(245, 158, 11, 0.15);
    color: var(--color-warning-400);
}

.results-actions {
    display: flex;
    gap: 8px;
}

.select-all-btn {
    padding: 6px 12px;
    border-radius: 6px;
    border: 1px solid var(--border-color);
    background: transparent;
    color: var(--text-secondary);
    font-size: 12px;
    cursor: pointer;
    transition: all 0.2s;
}

.select-all-btn:hover {
    background: var(--bg-card-hover);
    color: var(--text-primary);
}

.batch-download-btn {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 6px 12px;
    border-radius: 6px;
    border: none;
    background: var(--color-success-500);
    color: white;
    font-size: 12px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.2s;
}

.batch-download-btn:hover {
    background: var(--color-success-600);
}

/* Loading State */
.loading-state {
    display: flex;
    flex-direction: column;
    height: 100%;
    min-height: 0;
    gap: 16px;
    /* padding: 40px; remove padding to match main content */
    color: var(--text-secondary);
}

.empty-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 16px;
    padding: 40px;
    color: var(--text-secondary);
    text-align: center;
}

/* Skeleton Loading */
.skeleton-card {
    display: flex;
    align-items: center;
    gap: 12px;
}

.skeleton-card .ref-number {
    width: 40px;
    height: 24px;
    border-radius: 6px;
}

.skeleton-text {
    border-radius: 4px;
}

.skeleton-shimmer {
    background: linear-gradient(90deg,
            var(--color-neutral-200) 25%,
            var(--color-neutral-100) 50%,
            var(--color-neutral-200) 75%);
    background-size: 200% 100%;
    animation: shimmer 1.5s infinite;
}

[data-theme="dark"] .skeleton-shimmer {
    background: linear-gradient(90deg,
            var(--color-neutral-800) 25%,
            var(--color-neutral-700) 50%,
            var(--color-neutral-800) 75%);
    background-size: 200% 100%;
}

@keyframes shimmer {
    0% {
        background-position: 200% 0;
    }

    100% {
        background-position: -200% 0;
    }
}

/* References List */
.references-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
    overflow-y: auto;
    flex: 1;
    min-height: 0;
    padding-right: 4px;
    /* Avoid scrollbar overlap */
}

.reference-card {
    display: flex;
    align-items: flex-start;
    gap: 12px;
    padding: 12px;
    border: 1px solid var(--border-color);
    background: var(--bg-card);
    border-radius: 8px;
    transition: all 0.2s;
    cursor: default;
    width: 100%;
}

.reference-card:hover {
    border-color: var(--border-card-hover);
}

.reference-card.is-selectable {
    cursor: pointer;
}

.reference-card.is-selectable:hover {
    background: var(--bg-hover);
}

.reference-card.is-selected {
    border-color: var(--color-success-500);
    background: var(--color-success-50);
}

[data-theme="dark"] .reference-card.is-selected {
    background: rgba(34, 197, 94, 0.1);
}

.reference-card.is-unavailable {
    opacity: 0.5;
}



/* Reference Number */
.ref-number {
    display: flex;
    align-items: center;
    justify-content: center;
    min-width: 40px;
    height: 28px;
    background: var(--bg-badge);
    border-radius: 6px;
    font-size: 12px;
    font-weight: 600;
    color: var(--text-secondary);
    flex-shrink: 0;
}

.check-icon {
    color: var(--color-success-600);
}

/* Content */
.ref-content {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 4px;
}

.ref-title {
    font-size: 14px;
    font-weight: 500;
    color: var(--text-primary);
    line-height: 1.5;
    margin: 0;
}

.availability-badge {
    display: inline-block;
    vertical-align: middle;
    font-size: 10px;
    padding: 2px 6px;
    border-radius: 4px;
    font-weight: 600;
    text-transform: uppercase;
    margin-right: 6px;
}

.badge-arxiv {
    background: #b31b1b;
    color: white;
}

.badge-doi {
    background: var(--color-info-500);
    color: white;
}

.badge-pdf {
    background: var(--color-success-500);
    color: white;
}

.badge-link {
    background: var(--color-warning-100);
    color: var(--color-warning-700);
}

[data-theme="dark"] .badge-link {
    background: rgba(245, 158, 11, 0.2);
    color: var(--color-warning-400);
}

.badge-search {
    background: var(--color-neutral-200);
    color: var(--text-secondary);
}

[data-theme="dark"] .badge-search {
    background: var(--color-neutral-700);
}

.badge-found {
    background: var(--color-success-500);
    color: white;
}

.badge-notfound {
    background: var(--color-neutral-300);
    color: var(--text-tertiary);
}

[data-theme="dark"] .badge-notfound {
    background: var(--color-neutral-800);
    color: var(--text-tertiary);
}

.badge-unavailable {
    background: var(--color-neutral-200);
    color: var(--text-tertiary);
}

[data-theme="dark"] .badge-unavailable {
    background: var(--color-neutral-800);
}

.ref-meta {
    display: flex;
    gap: 12px;
    font-size: 12px;
    color: var(--text-secondary);
}

.ref-authors {
    max-width: 300px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.search-found {
    display: flex;
    align-items: center;
    gap: 4px;
    font-size: 11px;
    color: var(--color-success-600);
    margin-top: 4px;
}

/* Actions */
.ref-actions {
    display: flex;
    gap: 6px;
    align-items: center;
    flex-shrink: 0;
}

.action-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 32px;
    height: 32px;
    border-radius: 6px;
    border: 1px solid var(--border-color);
    background: var(--bg-card);
    color: var(--text-secondary);
    cursor: pointer;
    transition: all 0.2s;
    text-decoration: none;
}

.action-btn:hover:not(:disabled) {
    background: var(--bg-card-hover);
    color: var(--text-primary);
    border-color: var(--border-card-hover);
}

.action-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
}

.download-btn {
    color: var(--color-success-600);
    border-color: var(--color-success-300);
}

.download-btn:hover:not(:disabled) {
    background: var(--color-success-50);
    border-color: var(--color-success-500);
}

[data-theme="dark"] .download-btn:hover:not(:disabled) {
    background: rgba(34, 197, 94, 0.1);
}

.search-btn {
    color: var(--color-warning-600);
    border-color: var(--color-warning-300);
}

.search-btn:hover:not(:disabled) {
    background: var(--color-warning-50);
    border-color: var(--color-warning-500);
}

[data-theme="dark"] .search-btn:hover:not(:disabled) {
    background: rgba(245, 158, 11, 0.1);
}

.loader {
    width: 14px;
    height: 14px;
    border: 2px solid var(--border-color);
    border-top-color: var(--text-secondary);
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
}

@keyframes spin {
    to {
        transform: rotate(360deg);
    }
}

.spin {
    animation: spin 0.8s linear infinite;
}

.reference-card.is-fetching {
    border-color: var(--color-info-300);
}

.error-msg {
    width: 100%;
    font-size: 11px;
    color: var(--color-error-600);
    margin-top: 4px;
    padding-left: 52px;
}
</style>
