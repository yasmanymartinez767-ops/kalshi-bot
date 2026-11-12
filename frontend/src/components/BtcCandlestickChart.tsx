import { useEffect, useRef } from 'react'
import {
  createChart, CrosshairMode, LineStyle,
  type IChartApi, type ISeriesApi, type Time, type SeriesMarker,
} from 'lightweight-charts'
import type { BtcCandle } from '../types'
import { detectPatterns } from '../utils/candlePatterns'

type Props = {
  candles: BtcCandle[]
  showPatterns?: boolean
  viewKey?: string
  targetPrice?: number | null
  targetLabel?: string
}

const BG = '#071626'
const UP = '#00e69a'
const DOWN = '#ff4568'

export function BtcCandlestickChart({
  candles, showPatterns = true, viewKey, targetPrice, targetLabel = 'Target',
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const candleRef = useRef<ISeriesApi<'Candlestick'> | null>(null)
  const volumeRef = useRef<ISeriesApi<'Histogram'> | null>(null)
  const lastKeyRef = useRef(viewKey)
  const initializedRef = useRef(false)

  useEffect(() => {
    const container = containerRef.current
    if (!container) return
    const chart = createChart(container, {
      autoSize: true,
      layout: { background: { color: BG }, textColor: '#b8cbe0', fontSize: 11 },
      grid: {
        vertLines: { color: '#11263a' },
        horzLines: { color: '#11263a' },
      },
      crosshair: { mode: CrosshairMode.Normal },
      rightPriceScale: {
        borderColor: '#254158',
        autoScale: true,
        scaleMargins: { top: 0.07, bottom: 0.25 },
        minimumWidth: 64,
      },
      timeScale: {
        borderColor: '#254158',
        timeVisible: true,
        secondsVisible: false,
        rightOffset: 4,
        barSpacing: 9,
        minBarSpacing: 3,
        fixLeftEdge: false,
        lockVisibleTimeRangeOnResize: true,
      },
      handleScroll: { mouseWheel: true, pressedMouseMove: true, horzTouchDrag: true, vertTouchDrag: false },
      handleScale: { axisPressedMouseMove: true, mouseWheel: true, pinch: true },
    })
    const candleSeries = chart.addCandlestickSeries({
      upColor: UP, downColor: DOWN,
      borderUpColor: UP, borderDownColor: DOWN,
      wickUpColor: UP, wickDownColor: DOWN,
      priceLineVisible: true,
      priceLineStyle: LineStyle.Dashed,
      priceFormat: { type: 'price', precision: 2, minMove: 0.01 },
    })
    const volumeSeries = chart.addHistogramSeries({
      priceScaleId: '',
      priceFormat: { type: 'volume' },
      lastValueVisible: false,
      priceLineVisible: false,
    })
    volumeSeries.priceScale().applyOptions({ scaleMargins: { top: 0.82, bottom: 0 } })
    chartRef.current = chart
    candleRef.current = candleSeries
    volumeRef.current = volumeSeries
    initializedRef.current = false
    return () => {
      chartRef.current = null
      candleRef.current = null
      volumeRef.current = null
      chart.remove()
    }
  }, [])

  useEffect(() => {
    const chart = chartRef.current
    const series = candleRef.current
    const volume = volumeRef.current
    if (!chart || !series || !volume) return

    const changedInterval = lastKeyRef.current !== viewKey
    if (changedInterval) {
      initializedRef.current = false
      lastKeyRef.current = viewKey
    }
    const visibleRange = initializedRef.current && !changedInterval
      ? chart.timeScale().getVisibleLogicalRange()
      : null

    // Normalize, sort and deduplicate. Never manufacture missing candles.
    const valid = candles.filter(c =>
      Number.isFinite(c.time) && Number.isFinite(c.open) &&
      Number.isFinite(c.high) && Number.isFinite(c.low) &&
      Number.isFinite(c.close) && c.high >= Math.max(c.open, c.close) &&
      c.low <= Math.min(c.open, c.close) && c.high >= c.low
    )
    const unique = Array.from(new Map(valid.map(c => [c.time, c])).values())
      .sort((a, b) => a.time - b.time)

    series.setData(unique.map(c => ({
      time: c.time as Time,
      open: c.open, high: c.high, low: c.low, close: c.close,
    })))
    volume.setData(unique.map(c => ({
      time: c.time as Time,
      value: Math.max(0, Number.isFinite(c.volume) ? c.volume : 0),
      color: c.close >= c.open ? 'rgba(0,230,154,0.32)' : 'rgba(255,69,104,0.32)',
    })))

    const markers: SeriesMarker<Time>[] = showPatterns
      ? detectPatterns(unique).slice(-60).map(p => ({
          time: p.time as Time,
          position: p.bullish ? 'belowBar' : 'aboveBar',
          color: p.bullish ? UP : DOWN,
          shape: p.bullish ? 'arrowUp' : 'arrowDown',
          text: p.pattern,
          size: 1,
        }))
      : []
    series.setMarkers(markers)

    if (unique.length > 0) {
      if (visibleRange && Number.isFinite(visibleRange.from) && Number.isFinite(visibleRange.to)) {
        chart.timeScale().setVisibleLogicalRange(visibleRange)
      } else {
        // Display recent candles at readable width instead of compressing days of history.
        chart.timeScale().setVisibleLogicalRange({
          from: Math.max(-1, unique.length - 65),
          to: unique.length + 3,
        })
      }
      initializedRef.current = true
    }
  }, [candles, showPatterns, viewKey])

  useEffect(() => {
    const series = candleRef.current
    if (!series || targetPrice == null || !Number.isFinite(targetPrice)) return
    const line = series.createPriceLine({
      price: targetPrice, color: '#ffca59', lineWidth: 1,
      lineStyle: LineStyle.Dashed, axisLabelVisible: true, title: targetLabel,
    })
    return () => series.removePriceLine(line)
  }, [targetPrice, targetLabel])

  return (
    <div
      ref={containerRef}
      className="w-full h-full min-h-0"
      style={{ background: BG, touchAction: 'pan-x pinch-zoom' }}
      onDoubleClick={() => {
        const count = candles.length
        if (count > 0) chartRef.current?.timeScale().setVisibleLogicalRange({
          from: Math.max(-1, count - 65), to: count + 3,
        })
      }}
      aria-label="BTC candlestick chart. Drag to move, pinch to zoom, double tap to reset."
    />
  )
}
