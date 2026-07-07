import { DOMAINS } from '../data/themes'
import { TOP5_LAYOUT, BOTTOM5_LAYOUT, MID24_LAYOUT, type LayoutSlot } from '../data/templateLayout'
import type { RankedTheme } from '../lib/parseRanking'
import { illustrationSrc } from '../lib/illustrations'
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

      <MidLegend ranking={ranking} />
    </div>
  )
}

function MidLegend({ ranking }: { ranking: RankedTheme[] }) {
  const mid = ranking.filter((r) => r.rank >= 6 && r.rank <= 29)
  if (mid.length === 0) return null
  return (
    <ul className="gr__legend-list">
      {mid.map((item) => {
        const domain = DOMAINS[item.theme.domain]
        return (
          <li key={item.rank} className="gr__legend-item" style={{ borderColor: domain.color }}>
            <span className="gr__legend-rank" style={{ background: domain.color }}>
              {item.rank}
            </span>
            {item.theme.nameJa}
          </li>
        )
      })}
    </ul>
  )
}

function LargeBadge({ slot, item }: { slot: LayoutSlot; item?: RankedTheme }) {
  const domain = item ? DOMAINS[item.theme.domain] : null
  return (
    <div
      className="gr__large"
      style={{ left: `${slot.x}%`, top: `${slot.y}%`, width: `${slot.d}%` }}
    >
      <div className="gr__large-circle" style={domain ? { borderColor: domain.color } : undefined}>
        {item && <img src={illustrationSrc(item.theme.id)} alt={item.theme.nameJa} />}
      </div>
      {item && (
        <>
          <span className="gr__large-rank" style={{ background: domain!.color }}>
            {item.rank}
          </span>
          <span className="gr__large-name">{item.theme.nameJa}</span>
        </>
      )}
    </div>
  )
}

function SmallBadge({ slot, item }: { slot: LayoutSlot; item?: RankedTheme }) {
  const domain = item ? DOMAINS[item.theme.domain] : null
  return (
    <div
      className="gr__small"
      style={{ left: `${slot.x}%`, top: `${slot.y}%`, width: `${slot.d}%` }}
      title={item ? `${item.rank}. ${item.theme.nameJa}` : undefined}
    >
      <div
        className="gr__small-dot"
        style={domain ? { background: domain.color, borderColor: domain.color } : undefined}
      >
        {item?.rank}
      </div>
    </div>
  )
}
