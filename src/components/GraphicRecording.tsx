import { DOMAINS } from '../data/themes'
import { TOP5_LAYOUT, BOTTOM5_LAYOUT, MID24_LAYOUT, type LayoutSlot, type MidLayoutSlot } from '../data/templateLayout'
import type { RankedTheme } from '../lib/parseRanking'
import { illustrationSvgSrc } from '../lib/illustrations'
import { InlineSvg } from './InlineSvg'
import './GraphicRecording.css'

interface Props {
  ranking: RankedTheme[]
}

export function GraphicRecording({ ranking }: Props) {
  const byRank = new Map(ranking.map((r) => [r.rank, r]))

  return (
    <div className="gr">
      <div className="gr__canvas">
        <img className="gr__template" src={`${import.meta.env.BASE_URL}graphic-recording-template.png`} alt="" />

        {TOP5_LAYOUT.map((slot, i) => (
          <LargeBadge key={i} slot={slot} item={byRank.get(i + 1)} />
        ))}
        {MID24_LAYOUT.map((slot, i) => (
          <SmallBadge key={i} slot={slot} item={byRank.get(i + 6)} />
        ))}
        {BOTTOM5_LAYOUT.map((slot, i) => (
          <LargeBadge key={i} slot={slot} item={byRank.get(i + 30)} />
        ))}
      </div>
    </div>
  )
}

function LargeBadge({ slot, item }: { slot: LayoutSlot; item?: RankedTheme }) {
  const domain = item ? DOMAINS[item.theme.domain] : null
  return (
    <div className="gr__large" style={{ left: `${slot.x}%`, top: `${slot.y}%`, width: `${slot.d}%` }}>
      <div className="gr__large-circle" style={domain ? { borderColor: domain.color } : undefined}>
        {item && <InlineSvg className="gr__large-illustration" src={illustrationSvgSrc(item.theme.id)} />}
        {item && (
          <span className="gr__large-caption">
            <span className="gr__large-rank" style={{ background: domain!.color }}>
              {item.rank}
            </span>
            <span className="gr__large-name">{item.theme.nameJa}</span>
          </span>
        )}
      </div>
    </div>
  )
}

function SmallBadge({ slot, item }: { slot: LayoutSlot & Partial<MidLayoutSlot>; item?: RankedTheme }) {
  const domain = item ? DOMAINS[item.theme.domain] : null
  const lane = slot.lane ?? 0
  // Anchored to a fixed baseline (not this node's own y, which varies with
  // the ribbon's curve) so lanes never coincide in height by accident.
  const RIBBON_BASELINE_Y = 64
  const labelBottom = 100 - RIBBON_BASELINE_Y + lane * 2.6

  return (
    <>
      <div
        className="gr__small-dot"
        style={{
          left: `${slot.x}%`,
          top: `${slot.y}%`,
          width: `${slot.d}%`,
          ...(domain ? { background: domain.color, borderColor: domain.color } : undefined),
        }}
      />
      {item && (
        <span
          className="gr__small-label"
          style={{ left: `${slot.x}%`, bottom: `${labelBottom}%` }}
        >
          <span className="gr__small-rank" style={{ background: domain!.color }}>
            {item.rank}
          </span>
          {item.theme.nameJa}
        </span>
      )}
    </>
  )
}
