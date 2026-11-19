import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { fetchBtcCandles, fetchBtcMarket, fetchBtcHistory, fetchKalshiCandles, fetchYmcTechnical, type BtcInterval, type BtcLookback } from '../api'

import { BtcCandlestickChart } from './BtcCandlestickChart'
import { BtcProbabilityChart } from './BtcProbabilityChart'

type YmcSignal = { direction: string; votes: number | null; validated: boolean; reason: string; rsi14?: number; ema9?: number; ema21?: number; macd_hist?: number; as_of_utc: string; source: string; settlement_price_warning: string; early_watch?: string; early_watch_validated?: boolean; candle_context?: { pattern: string; sideways_watch: boolean; volume_ratio_20: number | null; volume_elevated: boolean; pattern_validated: boolean } }

// Future horizons are intentionally not inferred from the current 1m vote count.
// A probability requires a separate, calibrated 5m/10m/15m forecasting model.
function YmcHorizonScale({ valid }: { valid: boolean }) {
  return <div className="mt-2 grid grid-cols-3 gap-1.5" aria-label="Horizontes predictivos">
    {([5, 10, 15] as const).map(minutes => <div key={minutes} className="rounded border border-[#2b3948] px-2 py-1 flex items-center justify-between gap-1">
      <span translate="no" className="text-xs font-semibold text-slate-200">{minutes} min</span>
      <span className="text-[10px] text-slate-400">{valid ? 'EVALUANDO' : '—'}</span>
    </div>)}
  </div>
}

// The countdown must advance locally, independent of network/API response times.
function useClock(): number {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now()), 250)
    return () => window.clearInterval(id)
  }, [])
  return now
}

function EarlyExitRadar() {
  const clockNow = useClock()
  const [side, setSide] = useState<'YES' | 'NO'>('YES')
  const [entryCents, setEntryCents] = useState('')
  const [entryTicker, setEntryTicker] = useState('')
  const [entrySide, setEntrySide] = useState<'YES' | 'NO'>('YES')
  const [targetGainCents, setTargetGainCents] = useState<20 | 25 | 30>(20)
  const [bidHistory, setBidHistory] = useState<{ ticker: string; side: string; bid: number; at: number }[]>([])
  const { data, isError, dataUpdatedAt } = useQuery({
    queryKey: ['btc-market'], queryFn: fetchBtcMarket, refetchInterval: 1000,
  })
  const market = data?.market
  const bid = side === 'YES' ? market?.yes_bid : market?.no_bid
  const ask = side === 'YES' ? market?.yes_ask : market?.no_ask
  const timeLeftMs = market?.close_time ? Date.parse(market.close_time) - clockNow : NaN
  const active = Number.isFinite(timeLeftMs) && timeLeftMs > 0 &&
    !!market?.ticker && market.ticker.toUpperCase().includes('BTC')
  const fresh = !isError && !!market && !!dataUpdatedAt && Date.now() - dataUpdatedAt < 15000
  const quoted = fresh && active && typeof bid === 'number' && typeof ask === 'number' &&
    Number.isFinite(bid) && Number.isFinite(ask) && bid > 0 && ask > 0 && bid <= ask && ask <= 1
  const entry = entryCents.trim() === '' ? null : Number(entryCents)
  // Never apply a manually entered position to a different contract or YES/NO side.
  const entryValid = entry !== null && Number.isFinite(entry) && entry > 0 && entry < 100 &&
    entryTicker === market?.ticker && entrySide === side
  useEffect(() => {
    if (!quoted || !market || bid === undefined) return
    const at = Date.now()
    setBidHistory(previous => {
      const recent = previous.filter(p => p.ticker === market.ticker && p.side === side && at - p.at <= 120000)
      if (recent.length && at - recent[recent.length - 1].at < 5000) return recent
      return [...recent, { ticker: market.ticker, side, bid, at }].slice(-24)
    })
  }, [quoted, market?.ticker, side, bid, dataUpdatedAt])
  const history = bidHistory.filter(p => p.ticker === market?.ticker && p.side === side && Date.now() - p.at <= 120000)
  const oldest = history[0]
  const bidChangeCents = quoted && oldest && Date.now() - oldest.at >= 30000 ? (bid - oldest.bid) * 100 : null
  const recentThree = history.slice(-3)
  const persistentDrop = quoted && recentThree.length === 3 &&
    recentThree[2].at - recentThree[0].at >= 10000 &&
    recentThree[0].bid > recentThree[1].bid &&
    recentThree[1].bid > recentThree[2].bid &&
    (recentThree[0].bid - recentThree[2].bid) * 100 >= 2
  const gross = quoted && entryValid ? bid * 100 - entry : null
  const grossReturnPercent = gross !== null && entry !== null ? gross / entry * 100 : null
  const targetReached = gross !== null && gross > targetGainCents
  // Watch-only: a profitable bid is not a prediction that it will reverse.
  const exitWatch = gross === null ? 'SIN DATOS SUFICIENTES' :
    targetReached && persistentDrop ? 'ATENCIÓN · 3 CAÍDAS CONSECUTIVAS DEL BID' :
    targetReached && bidChangeCents !== null && bidChangeCents <= -3 ? 'ATENCIÓN · BID RETROCEDE 3¢ O MÁS' :
    targetReached && timeLeftMs <= 120000 ? 'BENEFICIO DISPONIBLE · VENCIMIENTO PRÓXIMO' :
    targetReached ? 'OBJETIVO ALCANZADO · VIGILAR BID' :
    gross > 0 ? 'POR DEBAJO DEL OBJETIVO · ESPERAR' :
    gross < 0 ? 'POR DEBAJO DE ENTRADA' : 'SIN BENEFICIO BRUTO'
  return (
    <div className="mt-2 rounded border border-[#254158] bg-[#071626] px-2 py-2" aria-label="Radar de salida anticipada">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="font-bold text-[#e4b95b]">RADAR SALIDA · KALSHI 15M</span>
        <span className="text-[#9db4ca]">{!active ? 'MERCADO NO ACTIVO' : quoted ? 'COTIZACIÓN DISPONIBLE' : 'SIN COTIZACIÓN VÁLIDA'}</span>
      </div>
      <div className="mt-1 flex flex-wrap items-center gap-2">
        <label className="text-[#9db4ca]">Contrato
          <select value={side} onChange={e => setSide(e.target.value as 'YES' | 'NO')} className="ml-1 rounded border border-[#254158] bg-[#041321] p-1 text-[#e0edff]">
            <option value="YES">YES</option><option value="NO">NO</option>
          </select>
        </label>
        <label className="text-[#9db4ca]">Entrada (¢)
          <input aria-label="Precio de entrada en centavos" type="number" min="1" max="99" step="0.1" value={entryCents} onChange={e => { setEntryCents(e.target.value); setEntryTicker(market?.ticker ?? ''); setEntrySide(side) }} placeholder="—" className="ml-1 w-16 rounded border border-[#254158] bg-[#041321] p-1 text-[#e0edff]" />
        </label>
        <label className="text-[#9db4ca]">Subida mínima
          <select aria-label="Ganancia objetivo en centavos" value={targetGainCents} onChange={e => setTargetGainCents(Number(e.target.value) as 20 | 25 | 30)} className="ml-1 rounded border border-[#254158] bg-[#041321] p-1 text-[#e0edff]">
            <option value={20}>Más de 20¢</option><option value={25}>Más de 25¢</option><option value={30}>Más de 30¢</option>
          </select>
        </label>
        {entryCents.trim() !== '' && !entryValid && <span className="text-[#e4b95b]">Entrada no válida para este contrato/lado: vuelve a introducirla</span>}
        <span>Tiempo restante: <strong>{active ? timeRemaining(market?.close_time, clockNow) : '—'}</strong></span>
        <span>Venta al bid: <strong className="text-[#e0edff]">{quoted ? (bid * 100).toFixed(1) + '¢' : '—'}</strong></span>
        <span>Spread: <strong>{quoted ? ((ask - bid) * 100).toFixed(1) + '¢' : '—'}</strong></span>
        <span>Movimiento bid (hasta 2m): <strong className={bidChangeCents !== null && bidChangeCents < 0 ? 'text-[#ef5350]' : 'text-[#9db4ca]'}>{bidChangeCents === null ? 'RECOPILANDO' : (bidChangeCents > 0 ? '+' : '') + bidChangeCents.toFixed(1) + '¢'}</strong></span>
        <span>Rentabilidad bruta: <strong className={targetReached ? 'text-[#26a69a]' : 'text-[#9db4ca]'}>{grossReturnPercent === null ? '—' : (grossReturnPercent >= 0 ? '+' : '') + grossReturnPercent.toFixed(1) + '%'}</strong></span>
        <span>Resultado bruto: <strong className={gross === null ? 'text-[#9db4ca]' : gross >= 0 ? 'text-[#26a69a]' : 'text-[#ef5350]'}>{gross === null ? '—' : (gross >= 0 ? '+' : '') + gross.toFixed(1) + '¢/contrato'}</strong></span>
      </div>
      <div className={`mt-1 text-[10px] font-bold ${targetReached ? 'text-[#e4b95b]' : 'text-[#9db4ca]'}`} role="status">Vigilancia de salida: {exitWatch}</div>
      <div className="mt-1 text-[10px] text-[#9598a1]">Caídas consecutivas: {quoted ? (persistentDrop ? '3 muestras descendentes (≥2¢)' : 'NO CONFIRMADAS') : 'SIN DATOS'} · Solo vigilancia, no señal predictiva validada.</div>
      <div className="mt-1 text-[10px] text-[#9598a1]">Objetivo de subida superior a 20¢ por contrato por defecto (ejemplo: entrar a 20¢ y salir por encima de 40¢), antes de comisiones; no equivale a beneficio neto. Estimación usando el mejor bid, sin deslizamiento ni garantía de ejecución. No detecta posiciones ni ejecuta ventas.</div>
    </div>
  )
}

function YmcSignalPanel() {
  const { data, isError, isPending } = useQuery<YmcSignal>({
    queryKey: ['ymc-technical'], queryFn: fetchYmcTechnical,
    refetchInterval: 5000, staleTime: 3000, retry: 1,
  })
  const timestamp = data?.as_of_utc ? Date.parse(data.as_of_utc) : NaN
  const valid = !isError && data?.validated === true && Number.isInteger(data?.votes) && data!.votes! >= 0 && data!.votes! <= 5 && Number.isFinite(timestamp) &&
    Date.now() - timestamp >= 0 && Date.now() - timestamp <= 150000
  const watch = valid ? data?.early_watch : undefined
  const context = valid ? data?.candle_context : undefined
  const insight = watch === 'POSIBLE_AGOTAMIENTO_ALCISTA' ? 'Posible giro bajista' :
    watch === 'POSIBLE_AGOTAMIENTO_BAJISTA' ? 'Posible giro alcista' :
    watch === 'INDECISION' ? 'Indecisión · esperar' :
    context?.sideways_watch ? 'Mercado lateral · esperar' :
    context?.pattern === 'RECHAZO_SUPERIOR' ? 'Presión bajista' :
    context?.pattern === 'RECHAZO_INFERIOR' ? 'Presión alcista' :
    valid ? 'Sin giro temprano confirmado' : 'Esperando datos válidos'
  const trend = valid && ['ALCISTA', 'BAJISTA', 'ESPERAR'].includes(data!.direction) ? data!.direction : 'ESPERAR'
  const ageSeconds = Number.isFinite(timestamp) ? Math.max(0, Math.floor((Date.now() - timestamp) / 1000)) : null
  return (
    <section className="shrink-0 border-b border-[#263443] bg-[#101923] px-3 py-2" aria-label="Señales IA" aria-live="polite">
      <div className="flex items-center justify-between gap-2">
        <span className="text-[11px] font-semibold text-slate-300">IA · BTC</span>
        <span className="text-[10px] text-slate-500">{valid ? `Consulta cada 5s · última vela ${ageSeconds ?? '—'}s` : isPending ? 'Conectando' : `Sin señal válida · ${data?.reason ?? 'indicadores incompletos'}`}</span>
      </div>
      {!valid && !isPending && <div role="status" className="mt-1 text-[11px] text-amber-300">SEÑAL SUSPENDIDA · No usar la tendencia para decisiones hasta validar las velas.</div>}
      <div className="mt-1 grid grid-cols-3 gap-2">
        <div className="rounded border border-[#2b3948] bg-[#0c1520] p-2">
          <div className="text-[10px] text-slate-400">TENDENCIA</div>
          <div className={`text-base font-bold ${trend === 'ALCISTA' ? 'text-emerald-400' : trend === 'BAJISTA' ? 'text-rose-400' : 'text-slate-200'}`}>
            {trend === 'ALCISTA' ? '↑ SUBE' : trend === 'BAJISTA' ? '↓ BAJA' : 'ESPERAR'}
          </div>
        </div>
        <div className="rounded border border-[#2b3948] bg-[#0c1520] p-2">
          <div className="text-[10px] text-slate-400">VOTOS</div>
          <div className="text-base font-bold text-slate-100">{valid ? data!.votes : '—'}/5</div>
        </div>
        <div className="rounded border border-[#2b3948] bg-[#0c1520] p-2">
          <div className="text-[10px] text-slate-400">RSI</div>
          <div className="text-base font-bold text-slate-100">{valid ? data!.rsi14?.toFixed(0) : '—'}</div>
        </div>
      </div>
      <div className="mt-2 flex items-center justify-between gap-2 text-xs">
        <span className="font-semibold text-slate-100">{insight}</span>
        <span className="shrink-0 text-[10px] text-slate-500">Vigilancia · no validada</span>
      </div>
      <div className="mt-1 text-[10px] text-slate-400">Patrón: {context?.pattern ?? "—"} · Volumen relativo: {typeof context?.volume_ratio_20 === "number" ? context.volume_ratio_20.toFixed(1) + "×" : "—"} · MACD: {valid && typeof data?.macd_hist === "number" ? data.macd_hist.toFixed(2) : "—"}</div>
      <YmcHorizonScale valid={false} />
      <details className="mt-1 text-[11px] text-slate-400">
        <summary className="cursor-pointer">Radar de salida · opcional</summary>
        <EarlyExitRadar />
      </details>
    </section>
  )
}

const POLL_MS = 1000 // 1Hz, per spec: orderbook, BTC price, and candles all refresh every second

function timeRemaining(closeTimeIso?: string, now = Date.now()): string {
  if (!closeTimeIso) return '—'
  const secs = Math.max(0, (new Date(closeTimeIso).getTime() - now) / 1000)
  const m = Math.floor(secs / 60)
  const s = Math.floor(secs % 60)
  return `${m}:${s.toString().padStart(2, '0')}`
}

// ── toolbar button ───────────────────────────────────────────────────────────

function ToolbarButton({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      onClick={onClick}
      translate="no"
      className={`px-2 py-1 text-[11px] font-medium rounded transition-colors ${
        active
          ? 'bg-[#2962ff] text-white'
          : 'text-[#9db4ca] hover:bg-[#18324b] hover:text-[#e0edff]'
      }`}
    >
      {children}
    </button>
  )
}

// ── header ────────────────────────────────────────────────────────────────────

function MarketHeader() {
  const clockNow = useClock()
  const { data } = useQuery({
    queryKey: ['btc-market'],
    queryFn: fetchBtcMarket,
    refetchInterval: POLL_MS,
  })
  const market = data?.market

  if (!market) {
    return (
      <div className="shrink-0 border-b border-[#254158] bg-[#071626] px-4 py-2 text-[11px] text-[#9db4ca]">
        No open KXBTC15M window right now
      </div>
    )
  }


  return (
    <div className="shrink-0 border-b border-[#254158] bg-[#071626] px-3 py-2" aria-label="Pronóstico IA a 15 minutos">
      <div className="flex items-center justify-between gap-2 text-[10px] text-[#9db4ca]">
        <span className="truncate">KALSHI BTC · 15M · {market.ticker}</span>
        <span className="shrink-0">Cierra en <strong className="text-[#e0edff]">{timeRemaining(market.close_time, clockNow)}</strong></span>
      </div>
      <div className="mt-1 grid grid-cols-2 gap-2">
        <div className="rounded border border-[#176b55] bg-[#0a2524] px-2 py-1.5">
          <div className="text-xs font-bold text-emerald-400">↑ SUBE</div>
          <div className="text-sm font-bold text-emerald-300">EN EVALUACIÓN</div>
          
        </div>
        <div className="rounded border border-[#823747] bg-[#29151f] px-2 py-1.5">
          <div className="text-xs font-bold text-rose-400">↓ BAJA</div>
          <div className="text-sm font-bold text-rose-300">EN EVALUACIÓN</div>
          
        </div>
      </div>
      <div className="mt-1 flex items-center justify-between gap-2 text-[10px] text-[#9db4ca]">
        <span>Volumen: {market.volume.toLocaleString(undefined, { maximumFractionDigits: 0 })}</span>
        <span>IA 15 min · pronóstico aún no calibrado</span>
      </div>
      <details className="mt-1 text-[10px] text-[#9db4ca]">
        <summary className="cursor-pointer">Referencia de liquidación</summary>
        Kalshi liquida según CF Benchmarks BRTI; las velas BTC/USD mostradas provienen de Coinbase y no son datos BRTI con licencia.
      </details>
    </div>
  )
}

// ── chart panel wrapper ───────────────────────────────────────────────────────

function ChartPanel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="h-full flex flex-col min-h-0">
      <div className="border-b border-[#254158] px-3 py-1 shrink-0 bg-[#071626]">
        <span className="text-[10px] text-[#9db4ca] font-medium uppercase tracking-wide">{title}</span>
      </div>
      <div className="flex-1 min-h-0">{children}</div>
    </div>
  )
}

// ── main panel ────────────────────────────────────────────────────────────────

const INTERVALS: { key: BtcInterval; label: string }[] = [
  { key: '1m', label: '1m' }, { key: '5m', label: '5m' }, { key: '15m', label: '15m' },
]
const LOOKBACKS: { key: BtcLookback; label: string }[] = [
  { key: '1d', label: '1D' }, { key: '3d', label: '3D' }, { key: '1w', label: '1W' }, { key: '1m', label: '1M' },
]

export function BtcMarketView() {
  const [interval, setInterval_] = useState<BtcInterval>('1m')
  const [lookback, setLookback] = useState<BtcLookback>('1d')
  const [historyRange, setHistoryRange] = useState<'1h' | '1d' | '1w' | '1m'>('1d')
  const [showPatterns, setShowPatterns] = useState(true)
  const [showExtraCharts, setShowExtraCharts] = useState(false)
  const viewKey = `${interval}-${lookback}`

  const { data: candles } = useQuery({
    queryKey: ['btc-candles', interval, lookback],
    queryFn: () => fetchBtcCandles(interval, lookback),
    refetchInterval: 5000,
  })

  const { data: kalshiCandles, isPending: kalshiCandlesPending, isError: kalshiCandlesError, error: kalshiCandlesFailure } = useQuery({
    queryKey: ['btc-kalshi-candles', historyRange],
    queryFn: () => fetchKalshiCandles(historyRange),
    refetchInterval: 15000,
    retry: 1,
  })

  const { data: snapshots, isPending: snapshotsPending, isError: snapshotsError, error: snapshotsFailure } = useQuery({
    queryKey: ['btc-history', historyRange],
    queryFn: () => fetchBtcHistory(historyRange),
    refetchInterval: 15000,
    retry: 1,
  })

  const { data: marketData } = useQuery({
    queryKey: ['btc-market'],
    queryFn: fetchBtcMarket,
    refetchInterval: POLL_MS,
  })

  return (
    <div className="flex-1 min-h-0 flex flex-col overflow-y-auto overscroll-y-contain lg:overflow-hidden bg-[#071626] text-[#e0edff]" style={{ fontFamily: "-apple-system, 'Trebuchet MS', Roboto, Ubuntu, sans-serif" }}>
      <MarketHeader />
      <YmcSignalPanel />

      {/* toolbar: TradingView-style filter row */}
      <div className="shrink-0 border-b border-[#254158] bg-[#071626] px-3 py-1.5 flex items-center gap-4 flex-wrap">
        <div className="flex items-center gap-0.5 border border-[#254158] rounded p-0.5">
          {INTERVALS.map(i => (
            <ToolbarButton key={i.key} active={interval === i.key} onClick={() => setInterval_(i.key)}>{i.label}</ToolbarButton>
          ))}
        </div>
        <div className="flex items-center gap-0.5 border border-[#254158] rounded p-0.5">
          {LOOKBACKS.map(l => (
            <ToolbarButton
              key={l.key}
              active={lookback === l.key}
              onClick={() => { setLookback(l.key); setHistoryRange(l.key === '3d' ? '1w' : l.key) }}
            >
              {l.label}
            </ToolbarButton>
          ))}
        </div>
        <ToolbarButton active={showPatterns} onClick={() => setShowPatterns(v => !v)}>
          Patrones
        </ToolbarButton>
        <ToolbarButton active={showExtraCharts} onClick={() => setShowExtraCharts(v => !v)}>
          {showExtraCharts ? "Ocultar gráficos extra" : "Ver gráficos extra"}
        </ToolbarButton>
        <div className="flex-1" />
        <span className="text-[10px] text-[#9598a1]">
          Kalshi historial · {snapshotsError ? 'Error puntos' : snapshotsPending ? 'Cargando puntos' : !snapshots?.length ? 'Sin puntos registrados' : `${snapshots.length} puntos`} · {kalshiCandlesError ? 'Error velas' : kalshiCandlesPending ? 'Cargando velas' : !kalshiCandles?.length ? 'Sin velas registradas' : `${kalshiCandles.length} velas`}
        </span>
      </div>

      {(snapshotsError || kalshiCandlesError) && (
        <div className="shrink-0 px-3 py-1 text-[11px] text-[#ef9a9a]" role="status">
          Historial Kalshi: {snapshotsError ? `puntos: ${snapshotsFailure instanceof Error ? snapshotsFailure.message : 'error de red'}` : ''}
          {kalshiCandlesError ? ` velas: ${kalshiCandlesFailure instanceof Error ? kalshiCandlesFailure.message : 'error de red'}` : ''}
        </div>
      )}

      {/* Prioritize one readable BTC chart on mobile; secondary charts are opt-in. */}
      <div className={`shrink-0 grid grid-cols-1 gap-0 lg:flex-1 lg:min-h-0 lg:overflow-y-auto ${showExtraCharts ? "lg:grid-cols-2 lg:grid-rows-2" : "lg:grid-cols-1"}`}>
        <div className="border-b border-r border-[#254158] min-h-0 h-[min(55vh,460px)] min-h-[280px] lg:h-auto">
          <ChartPanel title="BTC/USD Candlestick (Coinbase)">
            <BtcCandlestickChart candles={candles ?? []} showPatterns={showPatterns} viewKey={viewKey} />
          </ChartPanel>
        </div>

        {showExtraCharts && <div className="border-b border-[#254158] min-h-0 h-[320px] lg:h-auto">
          <ChartPanel title="BTC/USD vs. Kalshi Target (Candlestick)">
            <BtcCandlestickChart
              candles={candles ?? []}
              showPatterns={showPatterns}
              viewKey={viewKey}
              targetPrice={marketData?.market?.floor_strike}
              targetLabel="Target"
            />
          </ChartPanel>
        </div>}

        {showExtraCharts && <div className="border-r border-[#254158] min-h-0 h-[320px] lg:h-auto">
          <ChartPanel title="Kalshi YES Price (Candlestick, real orderbook OHLC)">
            <BtcCandlestickChart
              candles={kalshiCandles ?? []}
              showPatterns={showPatterns}
              viewKey={historyRange}
              targetPrice={0.5}
              targetLabel="50%"
            />
          </ChartPanel>
        </div>}

        {showExtraCharts && <div className="min-h-0 h-[320px] lg:h-auto">
          <ChartPanel title="Kalshi YES Probability (smoothed, orderbook mid)">
            <BtcProbabilityChart snapshots={snapshots ?? []} viewKey={historyRange} />
          </ChartPanel>
        </div>}
      </div>
    </div>
  )
}
