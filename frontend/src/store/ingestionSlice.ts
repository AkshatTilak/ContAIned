import type { StateCreator } from "zustand";
import type { IngestionJobResponse } from "../types/api";

export interface IngestionSettings {
  chunkStrategy: "FixedSizeChunking" | "RecursiveCharacterChunking" | "SemanticChunking";
  chunkSize: number;
  chunkOverlap: number;
  ocrCleanup: boolean;
  langFilter: boolean;
  extractMetadata: boolean;
  generateSummary: boolean;
  layoutOcr: boolean;
  entityLinking: boolean;
}

export interface IngestionSliceState {
  activeJobs: IngestionJobResponse[];
  uploadProgress: number | null;
  settings: IngestionSettings;
}

export interface IngestionSliceActions {
  addJob: (job: IngestionJobResponse) => void;
  updateJob: (jobId: string, updates: Partial<IngestionJobResponse>) => void;
  setUploadProgress: (progress: number | null) => void;
  clearJobs: () => void;
  updateSettings: (newSettings: Partial<IngestionSettings>) => void;
}

export type IngestionSlice = IngestionSliceState & IngestionSliceActions;

const defaultSettings: IngestionSettings = {
  chunkStrategy: "RecursiveCharacterChunking",
  chunkSize: 512,
  chunkOverlap: 64,
  ocrCleanup: true,
  langFilter: false,
  extractMetadata: true,
  generateSummary: false,
  layoutOcr: true,
  entityLinking: false,
};

export const createIngestionSlice: StateCreator<
  IngestionSlice,
  [],
  [],
  IngestionSlice
> = (set) => ({
  activeJobs: [],
  uploadProgress: null,
  settings: defaultSettings,
  addJob: (job) =>
    set((state) => {
      const exists = state.activeJobs.some((j) => j.job_id === job.job_id);
      if (exists) {
        return {
          activeJobs: state.activeJobs.map((j) =>
            j.job_id === job.job_id ? { ...j, ...job } : j
          ),
        };
      }
      return { activeJobs: [job, ...state.activeJobs] };
    }),
  updateJob: (jobId, updates) =>
    set((state) => ({
      activeJobs: state.activeJobs.map((j) =>
        j.job_id === jobId ? { ...j, ...updates } : j
      ),
    })),
  setUploadProgress: (uploadProgress) => set({ uploadProgress }),
  clearJobs: () => set({ activeJobs: [] }),
  updateSettings: (newSettings) =>
    set((state) => ({
      settings: { ...state.settings, ...newSettings },
    })),
});

