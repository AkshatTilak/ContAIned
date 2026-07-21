import type { StateCreator } from "zustand";
import type { IngestionJobResponse } from "../types/api";

export interface IngestionSliceState {
  activeJobs: IngestionJobResponse[];
  uploadProgress: number | null;
}

export interface IngestionSliceActions {
  addJob: (job: IngestionJobResponse) => void;
  updateJob: (jobId: string, updates: Partial<IngestionJobResponse>) => void;
  setUploadProgress: (progress: number | null) => void;
  clearJobs: () => void;
}

export type IngestionSlice = IngestionSliceState & IngestionSliceActions;

export const createIngestionSlice: StateCreator<
  IngestionSlice,
  [],
  [],
  IngestionSlice
> = (set) => ({
  activeJobs: [],
  uploadProgress: null,
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
});
