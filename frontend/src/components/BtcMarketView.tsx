import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { fetchBtcCandles, fetchBtcMarket, fetchBtcHistory, fetchKalshiCandles, fetchYmcTechnical, type BtcInterval, type BtcLookback } from '../api'

import { BtcCandlestickChart } from './BtcCandlestickChart'
import { BtcProbabilityChart } from './BtcProbabilityChart'

type YmcSignal = { direction: string; votes: number | null; validated: boolean; reason: string; rsi14?: number; ema9?: number; ema21?: number; macd_hist?: number; as_of_utc: string; source: string; settlement_price_warning: string; early_watch?: string; early_watch_validated?: boolean; candle_context?: { pattern: string; sideways_watch: boolean; volume_ratio_20: number | null; volume_elevated: boolean; pattern_validated: boolean } }

// Future horizons are intentionally not inferred from the current 1m vote count.
// A probability requires a separate, calibrated 5m/10m/15m forecasting model.
function YmcHorizonScale({ valid }: { valid: boolean }) {
  return (
    <div className="mt-2 grid grid-cols-3 gap-1.5" aria-label="Escala predictiva por horizonte">
      {([5, 10, 15] as const).map(minutes => (
        <div key={minutes} className="min-w-0 rounded border border-[#254158] bg-[#071626] px-2 py-1.5 text-center">
          <div className="text-[10px] font-bold text-[#e4b95b]">{minutes} MIN</div>
          <div className="text-[16px] font-bold tabular-nums text-[#9db4ca]">—%</div>
          <div className="text-[10px] text-[#9db4ca]">{valid ? 'EN EVALUACIÓN' : 'SIN DATOS'}</div>
        </div>
      ))}
      <div className="col-span-3 text-[10px] text-[#9598a1]">Probabilidad de SUBE/BAJA por horizonte: pendiente de modelo calibrado. No confundir votos técnicos con porcentajes.</div>
    </div>
  )
}

function EarlyExitRadar() {
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
  const timeLeftMs = market?.close_time ? Date.parse(market.close_time) - Date.now() : NaN
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
        <span>Tiempo restante: <strong>{active ? timeRemaining(market?.close_time) : '—'}</strong></span>
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
  const { data, isError, isPending, isFetching, dataUpdatedAt } = useQuery<YmcSignal>({
    queryKey: ['ymc-technical'],
    queryFn: fetchYmcTechnical,
    refetchInterval: 10000,
    staleTime: 5000,
    retry: 1,
  })
  const valid = !isError && data?.validated === true && Number.isFinite(Date.parse(data.as_of_utc)) && Date.now() - Date.parse(data.as_of_utc) >= 0 && Date.now() - Date.parse(data.as_of_utc) <= 150000
  const status = isPending ? 'CONECTANDO' : isError ? 'SIN CONEXIÓN' : !valid ? (data?.reason ?? 'DATOS NO VÁLIDOS') : isFetching ? 'ACTUALIZANDO' : 'DATOS VALIDADOS'
  const direction = valid ? data!.direction : 'ESPERAR'
  return (
    <div className="shrink-0 border-b border-[#254158] bg-[#041321] px-3 py-2 text-[11px]" translate="no" aria-live="polite">
      <div className="flex flex-wrap items-center gap-x-5 gap-y-1">
        <span className="font-bold text-[#e4b95b]">♛ YMC · IA TÉCNICA</span>
        <span className={direction === 'ALCISTA' ? 'text-[#26a69a] font-bold' : direction === 'BAJISTA' ? 'text-[#ef5350] font-bold' : 'text-[#9db4ca] font-bold'}>{direction}</span>
        <span>Votos: {valid ? data!.votes : '—'}/5</span>
        <span>EMA 9/21: {valid ? data!.ema9?.toFixed(2) : '—'} / {valid ? data!.ema21?.toFixed(2) : '—'}</span>
        <span>RSI 14: {valid ? data!.rsi14?.toFixed(1) : '—'}</span>
        <span>MACD (12,26,9): {valid ? data!.macd_hist?.toFixed(3) : '—'}</span>
        <span className="text-[#9db4ca]">Coinbase 1m · {status} {valid ? '· ' + data!.as_of_utc.slice(11, 19) + ' UTC' : ''}</span>
      </div>
      <YmcHorizonScale valid={valid} />
      <EarlyExitRadar />
      {valid && data?.early_watch && data.early_watch !== 'NINGUNA' && (
        <div className="mt-1 text-[11px] text-[#e4b95b]">Vigilancia temprana: {data.early_watch.split('_').join(' ')} · Patrón exploratorio, sin precisión validada</div>
      )}
      {valid && data?.candle_context && (
        <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-[11px]" aria-label="Análisis de velas cerradas">
          <span className="text-[#e4b95b]">Patrón 1m: {data.candle_context.pattern.split('_').join(' ')}</span>
          <span>Volumen / promedio 20m: {data.candle_context.volume_ratio_20 == null ? '—' : data.candle_context.volume_ratio_20.toFixed(2) + 'x'}</span>
          {data.candle_context.volume_elevated && <span className="text-[#e4b95b]">VOLUMEN ELEVADO</span>}
          {data.candle_context.sideways_watch && <span className="text-[#e4b95b]">POSIBLE MERCADO LATERAL · ESPERAR</span>}
          <span className="text-[#9db4ca]">Observación exploratoria, no predicción validada</span>
        </div>
      )}
      <div className="text-[10px] text-[#9598a1] mt-1">{dataUpdatedAt ? `Última consulta: ${new Date(dataUpdatedAt).toLocaleTimeString()}. ` : ""}Señal técnica informativa, no probabilidad ni recomendación de entrada. Coinbase spot ≠ referencia de liquidación Kalshi.</div>
    </div>
  )
}

const POLL_MS = 1000 // 1Hz, per spec: orderbook, BTC price, and candles all refresh every second

function usd(n: number | null | undefined, decimals = 2) {
  if (n === null || n === undefined) return '—'
  return `$${n.toLocaleString(undefined, { minimumFractionDigits: decimals, maximumFractionDigits: decimals })}`
}

function timeRemaining(closeTimeIso?: string): string {
  if (!closeTimeIso) return '—'
  const secs = Math.max(0, (new Date(closeTimeIso).getTime() - Date.now()) / 1000)
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

  const yesMidPct = ((market.yes_bid + market.yes_ask) / 2 * 100).toFixed(1)

  return (
    <div className="shrink-0 border-b border-[#254158] bg-[#071626] px-4 py-2 flex items-center gap-5 flex-wrap">
      <div>
        <span className="text-[13px] font-semibold text-[#e0edff]">
          {market.title}
        </span>
        <span className="ml-2 text-[10px] text-[#9db4ca]">{market.ticker}</span>
      </div>
      <div className="text-[11px]">
        <span className="text-[#9db4ca] mr-1">Target</span>
        <span className="text-[#ff9800] font-medium tabular-nums">{usd(market.floor_strike)}</span>
      </div>
      <div className="text-[11px]">
        <span className="text-[#9db4ca] mr-1">YES</span>
        <span className="text-[#26a69a] font-medium tabular-nums">{yesMidPct}%</span>
        <span className="text-[#9598a1] ml-1">
          ({(market.yes_bid * 100).toFixed(0)}/{(market.yes_ask * 100).toFixed(0)}c)
        </span>
      </div>
      <div className="text-[11px]">
        <span className="text-[#9db4ca] mr-1">Volume</span>
        <span className="text-[#e0edff] tabular-nums">{market.volume.toLocaleString(undefined, { maximumFractionDigits: 0 })}</span>
      </div>
      <div className="text-[11px]">
        <span className="text-[#9db4ca] mr-1">Closes in</span>
        <span className="text-[#e0edff] tabular-nums font-semibold">{timeRemaining(market.close_time)}</span>
      </div>
      <div className="flex-1" />
      <span className="text-[10px] text-[#9598a1]">Settles on CF Benchmarks BRTI · BTC price feed below is a Coinbase spot proxy, not licensed BRTI data</span>
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
  { key: '1h', label: '1H' }, { key: '6h', label: '6H' }, { key: '1d', label: '1D' },
]
const LOOKBACKS: { key: BtcLookback; label: string }[] = [
  { key: '1d', label: '1D' }, { key: '3d', label: '3D' }, { key: '1w', label: '1W' }, { key: '1m', label: '1M' },
]

export function BtcMarketView() {
  const [interval, setInterval_] = useState<BtcInterval>('1m')
  const [lookback, setLookback] = useState<BtcLookback>('1d')
  const [historyRange, setHistoryRange] = useState<'1h' | '1d' | '1w' | '1m'>('1d')
  const [showPatterns, setShowPatterns] = useState(true)
  const viewKey = `${interval}-${lookback}`

  const { data: candles } = useQuery({
    queryKey: ['btc-candles', interval, lookback],
    queryFn: () => fetchBtcCandles(interval, lookback),
    refetchInterval: POLL_MS,
  })

  const { data: kalshiCandles, isError: kalshiCandlesError, error: kalshiCandlesFailure } = useQuery({
    queryKey: ['btc-kalshi-candles', historyRange],
    queryFn: () => fetchKalshiCandles(historyRange),
    refetchInterval: 15000,
    retry: 1,
  })

  const { data: snapshots, isError: snapshotsError, error: snapshotsFailure } = useQuery({
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
          Pattern markers
        </ToolbarButton>
        <div className="flex-1" />
        <span className="text-[10px] text-[#9598a1]">
          Kalshi historial · {snapshotsError ? 'Error puntos' : `${snapshots?.length ?? 0} puntos`} · {kalshiCandlesError ? 'Error velas' : `${kalshiCandles?.length ?? 0} velas`}
        </span>
      </div>

      {(snapshotsError || kalshiCandlesError) && (
        <div className="shrink-0 px-3 py-1 text-[11px] text-[#ef9a9a]" role="status">
          Historial Kalshi: {snapshotsError ? `puntos: ${snapshotsFailure instanceof Error ? snapshotsFailure.message : 'error de red'}` : ''}
          {kalshiCandlesError ? ` velas: ${kalshiCandlesFailure instanceof Error ? kalshiCandlesFailure.message : 'error de red'}` : ''}
        </div>
      )}

      {/* 2x2 grid: all four charts share the same filters, theme, pattern markers, and view-state preservation */}
      <div className="shrink-0 grid grid-cols-1 auto-rows-[300px] lg:flex-1 lg:min-h-0 lg:overflow-y-auto lg:grid-cols-2 lg:grid-rows-2 lg:auto-rows-auto">
        <div className="border-b border-r border-[#254158] min-h-0 h-[440px] lg:h-auto">
          <ChartPanel title="BTC/USD Candlestick (Coinbase)">
            <BtcCandlestickChart candles={candles ?? []} showPatterns={showPatterns} viewKey={viewKey} />
          </ChartPanel>
        </div>

        <div className="border-b border-[#254158] min-h-0">
          <ChartPanel title="BTC/USD vs. Kalshi Target (Candlestick)">
            <BtcCandlestickChart
              candles={candles ?? []}
              showPatterns={showPatterns}
              viewKey={viewKey}
              targetPrice={marketData?.market?.floor_strike}
              targetLabel="Target"
            />
          </ChartPanel>
        </div>

        <div className="border-r border-[#254158] min-h-0">
          <ChartPanel title="Kalshi YES Price (Candlestick, real orderbook OHLC)">
            <BtcCandlestickChart
              candles={kalshiCandles ?? []}
              showPatterns={showPatterns}
              viewKey={historyRange}
              targetPrice={0.5}
              targetLabel="50%"
            />
          </ChartPanel>
        </div>

        <div className="min-h-0">
          <ChartPanel title="Kalshi YES Probability (smoothed, orderbook mid)">
            <BtcProbabilityChart snapshots={snapshots ?? []} viewKey={historyRange} />
          </ChartPanel>
        </div>
      </div>
    </div>
  )
}
