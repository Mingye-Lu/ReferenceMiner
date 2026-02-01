import { ref, watch } from "vue";

export type PdfViewMode = "single" | "continuous";

const PDF_SETTINGS_KEY = "refminer_pdf_settings";

interface PdfSettings {
  viewMode: PdfViewMode;
}

const defaultSettings: PdfSettings = {
  viewMode: "single",
};

// Global state
const settings = ref<PdfSettings>({ ...defaultSettings });

// Initialize from localStorage
const stored = localStorage.getItem(PDF_SETTINGS_KEY);
if (stored) {
  try {
    settings.value = { ...defaultSettings, ...JSON.parse(stored) };
  } catch (e) {
    console.warn("Failed to parse PDF settings", e);
  }
}

// Persist changes
watch(
  settings,
  (newSettings) => {
    localStorage.setItem(PDF_SETTINGS_KEY, JSON.stringify(newSettings));
  },
  { deep: true },
);

export function usePdfSettings() {
  const setViewMode = (mode: PdfViewMode) => {
    settings.value.viewMode = mode;
  };

  return {
    settings,
    setViewMode,
  };
}
