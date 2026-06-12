import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

// ---------- tipos (espejo de los serializers del backend) ----------

export interface ShapItem {
  feature: string
  shap: number
  value: number | null
}

export interface Signal {
  id: number
  date: string
  ticker: string
  company: string | null
  sector: string | null
  probability: number
  quality_score: number
  combined_score: number
  price: number
  sma200: number | null
  pct_vs_sma200: number | null
  status: 'new' | 'dismissed' | 'bought'
  shap: ShapItem[]
  quality_breakdown: Record<string, number>
}

export interface RuleState {
  return_pct: number
  stop_loss_price: number
  stop_loss_distance: number
  trailing_active: boolean
  trailing_stop_price: number | null
  peak_price: number
  days_held: number
  days_left: number
  take_profit_price: number
  partial_tp_done: boolean
}

export interface Position {
  id: number
  ticker: string
  opened_at: string
  entry_price: number
  shares: number
  status: 'open' | 'closed'
  last_price: number | null
  last_eval_date: string | null
  market_value: number
  pnl: number
  closed_at: string | null
  close_price: number | null
  notes: string | null
  rules: RuleState | null
}

export interface PortfolioResponse {
  positions: Position[]
  total_value: number
  n_open: number
  max_positions: number
  warnings: string[]
}

export interface Alert {
  id: number
  created_at: string
  type: string
  ticker: string | null
  position_id: number | null
  message: string
  severity: 'info' | 'warning' | 'critical'
  read: boolean
}

export interface FoldMetric {
  fold: number
  n_train: number
  n_val: number
  val_start: string
  val_end: string
  avg_precision: number | null
  val_base_rate: number
  precision_at_thr: number | null
  recall_at_thr: number | null
  signals_at_thr: number
}

export interface HealthSummary {
  model: {
    id: number
    trained_at: string
    threshold: number
    horizon_days: number
    min_return: number
    n_samples: number
    n_features: number
    metrics: {
      folds: FoldMetric[]
      oof: {
        threshold: number
        precision: number
        recall: number
        n_oof: number
        n_signals: number
        base_rate: number
      }
    }
    importances: Record<string, number>
  } | null
  drift: Partial<
    Record<
      'data' | 'prediction',
      { created_at: string; drifted: boolean; metric: number; detail: unknown }
    >
  >
  runs: {
    id: number
    kind: string
    status: string
    started_at: string
    finished_at: string | null
    detail: string
  }[]
  config: Record<string, number>
}

export interface ChartData {
  dates: string[]
  close: number[]
  sma200: (number | null)[]
}

export interface NewsItem {
  date: string
  headline: string
  source: string
  url: string
  sentiment: number | null
}

// ---------- fetch ----------

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
  if (!res.ok) {
    const body = await res.text()
    throw new Error(`${res.status}: ${body.slice(0, 200)}`)
  }
  return res.json()
}

// ---------- hooks ----------

export const useSignals = (days = 30) =>
  useQuery({ queryKey: ['signals', days], queryFn: () => api<Signal[]>(`/signals?days=${days}`) })

export function useSignalStatus() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, status }: { id: number; status: string }) =>
      api(`/signals/${id}/status`, { method: 'POST', body: JSON.stringify({ status }) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['signals'] }),
  })
}

export const useChart = (ticker: string | null) =>
  useQuery({
    queryKey: ['chart', ticker],
    queryFn: () => api<ChartData>(`/tickers/${ticker}/chart`),
    enabled: !!ticker,
  })

export const useNews = (ticker: string | null) =>
  useQuery({
    queryKey: ['news', ticker],
    queryFn: () => api<NewsItem[]>(`/tickers/${ticker}/news`),
    enabled: !!ticker,
    staleTime: 600_000,
  })

export const usePortfolio = (status = 'all') =>
  useQuery({
    queryKey: ['portfolio', status],
    queryFn: () => api<PortfolioResponse>(`/positions?status=${status}`),
  })

export function usePortfolioMutation() {
  const qc = useQueryClient()
  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ['portfolio'] })
    qc.invalidateQueries({ queryKey: ['alerts'] })
  }
  return {
    create: useMutation({
      mutationFn: (body: {
        ticker: string
        opened_at: string
        entry_price: number
        shares: number
        notes?: string
      }) => api('/positions', { method: 'POST', body: JSON.stringify(body) }),
      onSuccess: invalidate,
    }),
    close: useMutation({
      mutationFn: ({ id, ...body }: { id: number; close_price: number; shares?: number }) =>
        api(`/positions/${id}/close`, { method: 'POST', body: JSON.stringify(body) }),
      onSuccess: invalidate,
    }),
    remove: useMutation({
      mutationFn: (id: number) => api(`/positions/${id}`, { method: 'DELETE' }),
      onSuccess: invalidate,
    }),
  }
}

export const useAlerts = (unreadOnly = false) =>
  useQuery({
    queryKey: ['alerts', unreadOnly],
    queryFn: () => api<Alert[]>(`/alerts?unread_only=${unreadOnly}`),
    refetchInterval: 60_000,
  })

export function useAlertMutation() {
  const qc = useQueryClient()
  return {
    markRead: useMutation({
      mutationFn: (id: number) => api(`/alerts/${id}/read`, { method: 'POST' }),
      onSuccess: () => qc.invalidateQueries({ queryKey: ['alerts'] }),
    }),
    markAll: useMutation({
      mutationFn: () => api('/alerts/read-all', { method: 'POST' }),
      onSuccess: () => qc.invalidateQueries({ queryKey: ['alerts'] }),
    }),
  }
}

export const useHealth = () =>
  useQuery({ queryKey: ['health'], queryFn: () => api<HealthSummary>('/health/summary') })

export const usePipelineStatus = () =>
  useQuery({
    queryKey: ['pipeline-status'],
    queryFn: () => api<{ running: string | null }>('/pipeline/status'),
    refetchInterval: 5_000,
  })

export function usePipelineTrigger() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (kind: string) => api(`/pipeline/${kind}`, { method: 'POST' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['pipeline-status'] }),
  })
}
