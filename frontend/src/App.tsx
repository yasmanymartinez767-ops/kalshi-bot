import { BtcMarketView } from './components/BtcMarketView'

/** BTC-only, informational dashboard. No trading controls or order execution. */
export default function App() {
  return (
    <div className="h-[100dvh] min-h-0 flex flex-col bg-[#071626] text-[#e0edff] overflow-hidden">
      <header className="shrink-0 px-3 py-2 border-b border-[#254158] flex items-center justify-between">
        <strong className="text-sm tracking-wide text-amber-400">♛ YMC · BTC PREDICTOR AI PRO</strong>
        <span className="text-[11px] text-[#9db4ca]">BTC · 15M</span>
      </header>
      <BtcMarketView />
    </div>
  )
}
