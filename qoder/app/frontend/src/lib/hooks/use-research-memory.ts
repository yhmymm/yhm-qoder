import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiClient } from '@/lib/api/client'
import { QUERY_KEYS } from '@/lib/api/query-client'

// Types
export interface ResearchMemoryItem {
  id: string
  type: 'goal' | 'conclusion' | 'open_question' | 'next_step'
  content: string
  epistemic_status: 'supported' | 'hypothesis' | 'user_statement'
  evidence_indices?: number[]
  quote?: string
  created_at: string
  updated_at: string
  revision: number
  forgotten: boolean
}

export interface MemoryCandidate {
  type: 'goal' | 'conclusion' | 'open_question' | 'next_step'
  content: string
  epistemic_status: 'supported' | 'hypothesis' | 'user_statement'
  evidence_indices: number[]
  quote?: string
}

export interface DraftResponse {
  draft_id: string
  candidates: MemoryCandidate[]
  created_at: string
}

export interface ResearchReport {
  markdown: string
  sections: {
    goals: string
    findings: string
    open_questions: string
    next_steps: string
    references: string
  }
  generated_at: string
}

// API functions
const researchApi = {
  getMemories: async (notebookId: string): Promise<ResearchMemoryItem[]> => {
    const response = await apiClient.get(`/research/notebooks/${notebookId}/memories`)
    return response.data.memories
  },

  extractCandidates: async (notebookId: string, data: {
    source_ids?: string[]
    note_ids?: string[]
    user_instruction?: string
  }): Promise<{ candidates: MemoryCandidate[] }> => {
    const response = await apiClient.post(`/research/notebooks/${notebookId}/memory-extract`, data)
    return response.data
  },

  confirmCandidates: async (notebookId: string, items: Array<{
    draft_id: string
    draft_version: number
    operation_id?: string
  }>): Promise<{ confirmed: number }> => {
    const response = await apiClient.post(`/research/notebooks/${notebookId}/memory-confirmations`, { items })
    return response.data
  },

  updateMemory: async (notebookId: string, memoryId: string, data: {
    content: string
    revision: number
  }): Promise<ResearchMemoryItem> => {
    const response = await apiClient.put(`/research/notebooks/${notebookId}/memories/${memoryId}`, data)
    return response.data
  },

  forgetMemory: async (notebookId: string, memoryId: string): Promise<void> => {
    await apiClient.post(`/research/notebooks/${notebookId}/memories/${memoryId}/forget`)
  },

  generateReport: async (notebookId: string): Promise<ResearchReport> => {
    const response = await apiClient.post(`/research/notebooks/${notebookId}/report`)
    return response.data
  },

  resume: async (notebookId: string): Promise<{ context: string; memories: ResearchMemoryItem[] }> => {
    const response = await apiClient.post(`/research/notebooks/${notebookId}/resume`)
    return response.data
  },
}

// Hooks
export function useResearchMemories(notebookId: string) {
  return useQuery({
    queryKey: QUERY_KEYS.researchMemories(notebookId),
    queryFn: () => researchApi.getMemories(notebookId),
    enabled: !!notebookId,
  })
}

export function useExtractCandidates(notebookId: string) {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: (data: { source_ids?: string[]; note_ids?: string[]; user_instruction?: string }) =>
      researchApi.extractCandidates(notebookId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.researchMemories(notebookId) })
    },
  })
}

export function useConfirmMemoryCandidates(notebookId: string) {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: (items: Array<{ draft_id: string; draft_version: number; operation_id?: string }>) =>
      researchApi.confirmCandidates(notebookId, items),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.researchMemories(notebookId) })
    },
  })
}

export function useUpdateMemory(notebookId: string) {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: ({ memoryId, data }: { memoryId: string; data: { content: string; revision: number } }) =>
      researchApi.updateMemory(notebookId, memoryId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.researchMemories(notebookId) })
    },
  })
}

export function useForgetMemory(notebookId: string) {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: (memoryId: string) => researchApi.forgetMemory(notebookId, memoryId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.researchMemories(notebookId) })
    },
  })
}

export function useGenerateReport(notebookId: string) {
  return useMutation({
    mutationFn: () => researchApi.generateReport(notebookId),
  })
}

export function useResumeResearch(notebookId: string) {
  return useMutation({
    mutationFn: () => researchApi.resume(notebookId),
  })
}
