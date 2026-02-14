export type FileType = "pdf" | "docx" | "image" | "table" | "text";

export interface BibliographyAuthor {
  family?: string | null;
  given?: string | null;
  literal?: string | null;
  sequence?: number | null;
}

export interface Bibliography {
  docType?: string | null;
  language?: string | null;
  title?: string | null;
  subtitle?: string | null;
  authors?: BibliographyAuthor[];
  organization?: string | null;
  year?: number | null;
  date?: string | null;
  journal?: string | null;
  volume?: string | null;
  issue?: string | null;
  pages?: string | null;
  publisher?: string | null;
  place?: string | null;
  conference?: string | null;
  institution?: string | null;
  reportNumber?: string | null;
  standardNumber?: string | null;
  patentNumber?: string | null;
  url?: string | null;
  accessed?: string | null;
  doi?: string | null;
  doiStatus?: string | null;
  extraction?: Record<string, any> | null;
  verification?: Record<string, any> | null;
}

export interface ManifestEntry {
  relPath: string;
  fileType: FileType;
  title?: string | null;
  abstract?: string | null;
  pageCount?: number | null;
  sizeBytes?: number;
  sha256?: string;
  bibliography?: Bibliography | null;
}

export interface BoundingBox {
  page: number;
  x0: number;
  y0: number;
  x1: number;
  y1: number;
  charStart: number;
  charEnd: number;
}

export interface HighlightGroup {
  id?: string;
  boxes: BoundingBox[];
  color?: string;
}

export interface EvidenceChunk {
  chunkId: string;
  path: string;
  page?: number | null;
  section?: string | null;
  text: string;
  score: number;
  bbox?: BoundingBox[] | null;
}

export interface AnswerBlock {
  heading: string;
  body: string;
  citations: string[];
}

export interface TimelineStep {
  phase: string;
  message: string;
  startTime: number; // epoch ms
  details?: string;
  endTime?: number;
}

export interface ChatMessage {
  id: string;
  role: "user" | "ai";
  content: string;
  timestamp: number;
  timeline?: TimelineStep[];
  sources?: EvidenceChunk[];
  keywords?: string[];
  isStreaming?: boolean;
  completedAt?: number; // epoch ms when streaming completed
}

export interface ChatSession {
  id: string;
  title: string;
  lastActive: number;
  messageCount: number;
  preview: string;
}

export interface IndexStatus {
  indexed: boolean;
  lastIngest?: string | null;
  totalFiles?: number;
  totalChunks?: number;
}

export interface AskResponse {
  question: string;
  scope: string[];
  evidence: EvidenceChunk[];
  answer: AnswerBlock[];
  answerMarkdown: string;
  crosscheck: string;
}

// Upload types
export type UploadPhase =
  | "uploading"
  | "hashing"
  | "checking_duplicate"
  | "storing"
  | "extracting"
  | "indexing";
export type UploadStatus =
  | "pending"
  | "uploading"
  | "processing"
  | "complete"
  | "error"
  | "duplicate";

export type DeletePhase = "removing" | "rebuilding_index";
export type RenamePhase = "starting" | "renaming";
export type QueuePhase =
  | UploadPhase
  | DeletePhase
  | RenamePhase
  | "scanning"
  | "resetting"
  | "downloading";
export type QueueStatus = UploadStatus | "cancelled" | "dismissed";
export type QueueType = "upload" | "reprocess" | "delete" | "crawler_download" | "rename";
export type QueueScope = "bank" | "project";

export interface QueueJob {
  id: string;
  type: QueueType;
  scope: QueueScope;
  projectId?: string | null;
  name?: string | null;
  relPath?: string | null;
  status: QueueStatus;
  phase?: QueuePhase | null;
  progress?: number | null;
  error?: string | null;
  duplicatePath?: string | null;
  createdAt: number;
  updatedAt: number;
}

export interface UploadProgress {
  phase: UploadPhase;
  percent?: number;
}

export interface UploadResult {
  success: boolean;
  relPath: string;
  sha256: string;
  status: "processed" | "duplicate" | "replaced" | "error";
  message?: string;
  manifestEntry?: ManifestEntry;
  duplicatePath?: string;
}

export interface UploadItem {
  id: string;
  file: File;
  status: UploadStatus;
  progress: number;
  phase?: UploadPhase;
  error?: string;
  duplicatePath?: string;
  result?: UploadResult;
  bibliography?: Bibliography | null;
}

export interface UploadQueueItem {
  id: string;
  name: string;
  status: UploadStatus;
  progress: number;
  phase?: UploadPhase;
  error?: string;
  duplicatePath?: string;
}

export interface DuplicateCheck {
  isDuplicate: boolean;
  existingPath?: string | null;
  existingEntry?: ManifestEntry | null;
}

export interface DeleteResult {
  success: boolean;
  removedChunks: number;
  message: string;
}

export interface BatchDeleteFileResult {
  relPath: string;
  success: boolean;
  removedChunks?: number;
  error?: string;
}

export interface BatchDeleteResult {
  success: boolean;
  deletedCount: number;
  failedCount: number;
  totalChunksRemoved: number;
  results: BatchDeleteFileResult[];
}

export interface DeleteEventHandler {
  onFile?: (data: { relPath: string; status: string; phase?: string }) => void;
  onComplete?: (data: { relPath: string; removedChunks: number }) => void;
  onError?: (code: string, message: string) => void;
}

export interface BatchDeleteEventHandler {
  onStart?: (totalFiles: number) => void;
  onFile?: (data: {
    relPath: string;
    status: string;
    phase?: string;
    index?: number;
    total?: number;
  }) => void;
  onComplete?: (data: {
    deletedCount: number;
    failedCount: number;
    results: BatchDeleteFileResult[];
  }) => void;
  onError?: (code: string, message: string) => void;
}

// Project types
export interface Project {
  id: string;
  name: string;
  rootPath: string;
  createdAt: number;
  lastActive: number;
  fileCount: number;
  noteCount: number;
  description?: string;
  icon?: string;
  selectedFiles?: string[];
}

export interface ProjectCreate {
  name: string;
  description?: string;
}

// Settings types
export type CitationCopyFormat =
  | "apa"
  | "mla"
  | "chicago"
  | "gbt7714"
  | "numeric";

export interface Settings {
  activeProvider: string;
  providerKeys: Record<string, { hasKey: boolean; maskedKey: string | null }>;
  providerSettings: Record<string, { baseUrl: string; model: string }>;
  baseUrl: string;
  model: string;
  citationCopyFormat: CitationCopyFormat;
}

export interface BalanceInfo {
  currency: string;
  totalBalance: string;
  grantedBalance: string;
  toppedUpBalance: string;
}

export interface ValidateResult {
  valid: boolean;
  error?: string;
  isAvailable?: boolean;
  balanceInfos?: BalanceInfo[];
}

export interface UpdateCheck {
  repo: string;
  current: {
    version: string;
  };
  latest: {
    version?: string | null;
    url?: string | null;
    source?: string | null;
  };
  isUpdateAvailable: boolean;
  checkedAt?: number;
  error?: string | null;
}

// Crawler types
export interface CrawlerEngineConfig {
  enabled: boolean;
  rate_limit: number;
  timeout: number;
}

export type CrawlerAuthType =
  | "none"
  | "cookie_header"
  | "bearer"
  | "api_key"
  | "custom_headers";

export interface CrawlerEngineAuthProfile {
  authType: CrawlerAuthType;
  hasSecret: boolean;
  maskedSecret: string | null;
  headerNames: string[];
  updatedAt: number | null;
}

export type RefIdentMode = "string_only" | "string_then_ocr" | "ocr_only";

export interface CrawlerConfig {
  enabled: boolean;
  auto_download: boolean;
  max_results_per_engine: number;
  timeout_seconds: number;
  preset: CrawlerPresetName;
  engines: Record<string, CrawlerEngineConfig>;
  ref_ident_mode: RefIdentMode;
}

export interface CrawlerSearchResult {
  hash: string;
  title: string;
  authors: string[];
  year: number | null;
  abstract: string | null;
  doi: string | null;
  url: string | null;
  pdf_url: string | null;
  source: string;
  citations: number | null;
}

export interface CrawlerSearchQuery {
  query: string;
  max_results?: number;
  engines?: string[];
  year_from?: number | null;
  year_to?: number | null;
  sort_by?: "relevance" | "date" | "citations";
  deep_crawl?: boolean;
  deep_crawl_max_papers?: number;
}

export interface CrawlerDownloadResult {
  hash: string;
  success: boolean;
  path: string | null;
  error: string | null;
}

export type CrawlerPresetName =
  | "balanced"
  | "fast"
  | "thorough"
  | "minimal"
  | "custom";

export interface CrawlerPreset {
  name: CrawlerPresetName;
  label: string;
  description: string;
  enabledEngines: string[];
  rateLimit: number;
  timeout: number;
  maxResults: number;
  isCustom?: boolean;
}

export interface CrawlerStats {
  totalSearches: number;
  totalDownloads: number;
  failedDownloads: number;
  perEngineStats: Record<
    string,
    { searches: number; downloads: number; failures: number }
  >;
  lastUpdated: number | null;
}

export type ConnectionStatus = "unknown" | "testing" | "success" | "failed";

// OCR types
export interface OcrModelInfo {
  label: string;
  size: string;
  overhead: string;
  is_downloadable: boolean;
  installed?: boolean;
}

export interface OcrConfig {
  model: string;
  base_url?: string;
  api_key?: string;
}

export interface OcrSettingsResponse {
  config: OcrConfig;
  models: Record<string, OcrModelInfo>;
}
