'use client'

import { useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Textarea } from '@/components/ui/textarea'
import { useResearchMemories, useUpdateMemory, useForgetMemory, useExtractCandidates, useConfirmMemoryCandidates, ResearchMemoryItem, DraftResponse, MemoryCandidate } from '@/lib/hooks/use-research-memory'
import { apiClient } from '@/lib/api/client'
import { Edit2, Trash2, RotateCcw, Lightbulb, Target, HelpCircle, ArrowRight, Check, X, Loader2 } from 'lucide-react'
import { useTranslation } from '@/lib/hooks/use-translation'
import { toast } from 'sonner'

interface ResearchMemoryPanelProps {
  notebookId: string
}

const typeIcons = {
  goal: Target,
  conclusion: Lightbulb,
  open_question: HelpCircle,
  next_step: ArrowRight,
}

const typeLabels = {
  goal: '研究目标',
  conclusion: '阅读结论',
  open_question: '未解决问题',
  next_step: '下一步计划',
}

const typeColors = {
  goal: 'bg-blue-100 text-blue-800 border-blue-200',
  conclusion: 'bg-green-100 text-green-800 border-green-200',
  open_question: 'bg-yellow-100 text-yellow-800 border-yellow-200',
  next_step: 'bg-purple-100 text-purple-800 border-purple-200',
}

export function ResearchMemoryPanel({ notebookId }: ResearchMemoryPanelProps) {
  const { t } = useTranslation()
  const { data: memories, isLoading, error, refetch } = useResearchMemories(notebookId)
  const updateMemory = useUpdateMemory(notebookId)
  const forgetMemory = useForgetMemory(notebookId)
  const extractCandidates = useExtractCandidates(notebookId)
  const confirmCandidates = useConfirmMemoryCandidates(notebookId)
  
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editContent, setEditContent] = useState('')
  const [showForgotten, setShowForgotten] = useState(false)
  const [draft, setDraft] = useState<DraftResponse | null>(null)
  const [confirmedIndices, setConfirmedIndices] = useState<Set<number>>(new Set())
  const [rejectedIndices, setRejectedIndices] = useState<Set<number>>(new Set())
  const [editingCandidateIndex, setEditingCandidateIndex] = useState<number | null>(null)
  const [editCandidateContent, setEditCandidateContent] = useState('')

  const handleEdit = (memory: ResearchMemoryItem) => {
    setEditingId(memory.id)
    setEditContent(memory.content)
  }

  const handleSaveEdit = async (memory: ResearchMemoryItem) => {
    try {
      await updateMemory.mutateAsync({
        memoryId: memory.id,
        data: { content: editContent, revision: memory.revision }
      })
      setEditingId(null)
      toast.success('记忆已更新')
    } catch (err) {
      toast.error('更新失败，可能存在并发冲突')
    }
  }

  const handleForget = async (memoryId: string) => {
    if (!confirm('确定要遗忘这条记忆吗？遗忘后历史仍可追溯，但不再参与新会话接续。')) return
    
    try {
      await forgetMemory.mutateAsync(memoryId)
      toast.success('记忆已遗忘')
    } catch (err) {
      toast.error('遗忘失败')
    }
  }

  const handleCreateDraft = async () => {
    try {
      // 获取当前 Notebook 的 Sources 和 Notes
      const [sourcesResponse, notesResponse] = await Promise.all([
        apiClient.get(`/sources`, { params: { notebook_id: notebookId, limit: 50 } }),
        apiClient.get(`/notes`, { params: { notebook_id: notebookId } })
      ])
      
      const sourceIds = (sourcesResponse.data?.sources || []).map((s: any) => s.id)
      const noteIds = (notesResponse.data || []).map((n: any) => n.id)
      
      if (sourceIds.length === 0 && noteIds.length === 0) {
        toast.error('当前 Notebook 没有资料或笔记，请先添加 Sources 或 Notes')
        return
      }
      
      const result = await extractCandidates.mutateAsync({
        source_ids: sourceIds,
        note_ids: noteIds
      })
      
      setDraft({
        draft_id: 'extract-' + Date.now(),
        candidates: result.candidates,
        created_at: new Date().toISOString()
      })
      setConfirmedIndices(new Set())
      setRejectedIndices(new Set())
      toast.success(`从 ${sourceIds.length} 个资料和 ${noteIds.length} 个笔记中提取了 ${result.candidates.length} 条候选记忆`)
    } catch (err: any) {
      const errorMsg = err?.response?.data?.detail || err?.message || '提取候选记忆失败'
      toast.error(errorMsg)
    }
  }

  const handleConfirmCandidate = async (candidate: MemoryCandidate, index: number) => {
    if (!draft) return
    
    try {
      // 构造确认项
      const item = {
        draft_id: draft.draft_id,
        draft_version: 1,
        operation_id: `op-${index}`
      }
      
      await confirmCandidates.mutateAsync([item])
      setConfirmedIndices(prev => new Set(prev).add(index))
      setEditingCandidateIndex(null)
      toast.success('记忆已确认')
      
      // 如果所有候选都已处理，刷新记忆列表
      if (confirmedIndices.size + 1 + rejectedIndices.size === draft.candidates.length) {
        setTimeout(() => {
          refetch()
          setDraft(null)
        }, 500)
      }
    } catch (err) {
      toast.error('确认失败')
    }
  }

  const handleRejectCandidate = (index: number) => {
    setRejectedIndices(prev => new Set(prev).add(index))
    toast.success('候选已拒绝')
    
    // 如果所有候选都已处理，刷新记忆列表
    if (confirmedIndices.size + rejectedIndices.size + 1 === draft?.candidates.length) {
      setTimeout(() => {
        refetch()
        setDraft(null)
      }, 500)
    }
  }

  if (isLoading) {
    return <div className="text-sm text-muted-foreground">加载中...</div>
  }

  if (error) {
    return <div className="text-sm text-red-600">加载失败：{(error as Error).message}</div>
  }

  const activeMemories = memories?.filter(m => !m.forgotten) || []
  const forgottenMemories = memories?.filter(m => m.forgotten) || []

  return (
    <div className="space-y-4">
      {/* Header with Create Draft Button */}
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold">研究记忆 ({activeMemories.length})</h3>
        <div className="flex gap-2">
          {!draft && (
            <Button
              size="sm"
              onClick={handleCreateDraft}
              disabled={extractCandidates.isPending}
              className="text-xs"
            >
              {extractCandidates.isPending ? (
                <>
                  <Loader2 className="h-3 w-3 mr-1 animate-spin" />
                  提取中...
                </>
              ) : (
                <>
                  <Lightbulb className="h-3 w-3 mr-1" />
                  提取候选记忆
                </>
              )}
            </Button>
          )}
          {forgottenMemories.length > 0 && (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setShowForgotten(!showForgotten)}
            className="text-xs"
          >
            {showForgotten ? '隐藏已遗忘' : `显示已遗忘 (${forgottenMemories.length})`}
          </Button>
        )}
        </div>
      </div>

      {/* Candidate Memories Section */}
      {draft && (
        <div className="space-y-3 p-4 bg-blue-50 border border-blue-200 rounded-lg">
          <div className="flex items-center justify-between">
            <h4 className="text-sm font-semibold text-blue-900">
              候选记忆 ({draft.candidates.length})
            </h4>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setDraft(null)}
              className="text-xs"
            >
              取消
            </Button>
          </div>
          <div className="space-y-2">
            {draft.candidates.map((candidate, index) => {
              const Icon = typeIcons[candidate.type]
              const isConfirmed = confirmedIndices.has(index)
              const isRejected = rejectedIndices.has(index)
              const isEditing = editingCandidateIndex === index
              
              if (isRejected) return null
              
              return (
                <Card key={index} className={isConfirmed ? 'bg-green-50 border-green-200' : ''}>
                  <CardContent className="pt-4">
                    {isEditing ? (
                      <div className="space-y-2">
                        <Textarea
                          value={editCandidateContent}
                          onChange={(e) => setEditCandidateContent(e.target.value)}
                          rows={3}
                          className="text-sm"
                        />
                        <div className="flex gap-2">
                          <Button
                            size="sm"
                            onClick={() => handleConfirmCandidate(candidate, index)}
                            disabled={confirmCandidate.isPending}
                          >
                            保存并确认
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => setEditingCandidateIndex(null)}
                          >
                            取消
                          </Button>
                        </div>
                      </div>
                    ) : (
                      <>
                        <div className="flex items-start gap-2 mb-2">
                          <Badge variant="outline" className={typeColors[candidate.type]}>
                            <Icon className="h-3 w-3 mr-1" />
                            {typeLabels[candidate.type]}
                          </Badge>
                          {isConfirmed && (
                            <Badge variant="secondary" className="bg-green-100 text-green-800">
                              <Check className="h-3 w-3 mr-1" />
                              已确认
                            </Badge>
                          )}
                        </div>
                        <p className="text-sm mb-2">{candidate.content}</p>
                        {candidate.quote && (
                          <div className="text-xs text-muted-foreground border-l-2 pl-2 mb-2 italic">
                            &ldquo;{candidate.quote}&rdquo;
                          </div>
                        )}
                        {candidate.evidence_refs && candidate.evidence_refs.length > 0 && (
                          <div className="text-xs text-muted-foreground mb-3">
                             证据来源: {candidate.evidence_refs.map((ref: any, i: number) => ref.source_id || ref.id || `#${i+1}`).join(', ')}
                          </div>
                        )}
                        {!isConfirmed && (
                          <div className="flex gap-2">
                            <Button
                              size="sm"
                              onClick={() => handleConfirmCandidate(candidate, index)}
                              disabled={confirmCandidates.isPending}
                              className="text-xs"
                            >
                              <Check className="h-3 w-3 mr-1" />
                              确认
                            </Button>
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => {
                                setEditingCandidateIndex(index)
                                setEditCandidateContent(candidate.content)
                              }}
                              className="text-xs"
                            >
                              <Edit2 className="h-3 w-3 mr-1" />
                              修订后确认
                            </Button>
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => handleRejectCandidate(index)}
                              className="text-xs text-red-600 hover:text-red-700"
                            >
                              <X className="h-3 w-3 mr-1" />
                              拒绝
                            </Button>
                          </div>
                        )}
                      </>
                    )}
                  </CardContent>
                </Card>
              )
            })}
          </div>
        </div>
      )}

      {/* Active Memories Section */}
      {activeMemories.length === 0 && !draft ? (
        <div className="text-sm text-muted-foreground text-center py-8">
          暂无研究记忆。通过聊天或资料分析来创建记忆。
        </div>
      ) : (
        <div className="space-y-2">
          {activeMemories.map((memory, index) => {
            const Icon = typeIcons[memory.type]
            return (
              <Card key={memory.id || `memory-${index}`} className="relative">
                <CardContent className="pt-4">
                  {editingId === memory.id ? (
                    <div className="space-y-2">
                      <Textarea
                        value={editContent}
                        onChange={(e) => setEditContent(e.target.value)}
                        rows={3}
                        className="text-sm"
                      />
                      <div className="flex gap-2">
                        <Button
                          size="sm"
                          onClick={() => handleSaveEdit(memory)}
                          disabled={updateMemory.isPending}
                        >
                          保存
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => setEditingId(null)}
                        >
                          取消
                        </Button>
                      </div>
                    </div>
                  ) : (
                    <>
                      <div className="flex items-start gap-2 mb-2">
                        <Badge variant="outline" className={typeColors[memory.type]}>
                          <Icon className="h-3 w-3 mr-1" />
                          {typeLabels[memory.type]}
                        </Badge>
                        <Badge variant="secondary" className="text-xs">
                          rev.{memory.revision}
                        </Badge>
                      </div>
                      <p className="text-sm mb-3">{memory.content}</p>
                      {memory.quote && (
                        <div className="text-xs text-muted-foreground border-l-2 pl-2 mb-3 italic">
                          &ldquo;{memory.quote}&rdquo;
                        </div>
                      )}
                      <div className="flex gap-2">
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => handleEdit(memory)}
                          className="text-xs"
                        >
                          <Edit2 className="h-3 w-3 mr-1" />
                          修订
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => handleForget(memory.id)}
                          className="text-xs text-red-600 hover:text-red-700"
                        >
                          <Trash2 className="h-3 w-3 mr-1" />
                          遗忘
                        </Button>
                      </div>
                    </>
                  )}
                </CardContent>
              </Card>
            )
          })}
        </div>
      )}

      {showForgotten && forgottenMemories.length > 0 && (
        <div className="space-y-2 pt-4 border-t">
          <h4 className="text-sm font-semibold text-muted-foreground">已遗忘的记忆</h4>
          {forgottenMemories.map((memory, index) => {
            const Icon = typeIcons[memory.type]
            return (
              <Card key={memory.id || `forgotten-${index}`} className="opacity-60">
                <CardContent className="pt-4">
                  <div className="flex items-start gap-2 mb-2">
                    <Badge variant="outline" className={`${typeColors[memory.type]} line-through`}>
                      <Icon className="h-3 w-3 mr-1" />
                      {typeLabels[memory.type]}
                    </Badge>
                    <Badge variant="secondary" className="text-xs bg-red-100 text-red-800">
                      已遗忘
                    </Badge>
                  </div>
                  <p className="text-sm line-through text-muted-foreground">{memory.content}</p>
                </CardContent>
              </Card>
            )
          })}
        </div>
      )}
    </div>
  )
}
