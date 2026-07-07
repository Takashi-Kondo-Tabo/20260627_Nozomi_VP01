import { useMemo, useRef } from 'react'
import { DOMAINS } from '../data/themes'
import type { RankedTheme } from '../lib/parseRanking'
import { illustrationSrc } from '../lib/illustrations'
import { buildSmoothSegments } from '../lib/smoothPath'
import { useFlowPositions } from '../lib/useFlowPositions'
import './GraphicRecording.css'

interface Props {
  ranking: RankedTheme[]
}

export function GraphicRecording({ ranking }: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const itemRefs = useRef<(HTMLElement | null)[]>([])
  itemRefs.current = []

  const registerRef = (el: HTMLElement | null) => {
    itemRefs.current.push(el)
  }

  const points = useFlowPositions(containerRef, itemRefs, [ranking])

  const segments = useMemo(() => buildSmoothSegments(points), [points])

  const top = ranking.filter((r) => r.rank <= 5)
  const middle = ranking.filter((r) => r.rank >= 6 && r.rank <= 29)
  const bottom = ranking.filter((r) => r.rank >= 30)

  return (
    <div className="gr" ref={containerRef}>
      <svg className="gr__svg">
        {segments.map((d, i) => {
          const theme = ranking[i]?.theme
          const color = theme ? DOMAINS[theme.domain].color : '#ccc'
          return (
            <path
              key={i}
              d={d}
              fill="none"
              stroke={color}
              strokeWidth={10}
              strokeLinecap="round"
              opacity={0.35}
            />
          )
        })}
      </svg>

      <div className="gr__legend">
        {Object.values(DOMAINS).map((d) => (
          <span key={d.id} className="gr__legend-item">
            <span className="gr__legend-dot" style={{ background: d.color }} />
            {d.labelJa}
          </span>
        ))}
      </div>

      {top.length > 0 && (
        <div className="gr__section">
          {top.map((item) => (
            <LargeBadge key={item.rank} item={item} registerRef={registerRef} />
          ))}
        </div>
      )}

      {middle.length > 0 && (
        <>
          <p className="gr__divider">6 〜 29 位</p>
          <div className="gr__section gr__section--dense">
            {middle.map((item) => (
              <SmallBadge key={item.rank} item={item} registerRef={registerRef} />
            ))}
          </div>
        </>
      )}

      {bottom.length > 0 && (
        <div className="gr__section">
          {bottom.map((item) => (
            <LargeBadge key={item.rank} item={item} registerRef={registerRef} />
          ))}
        </div>
      )}
    </div>
  )
}

function LargeBadge({
  item,
  registerRef,
}: {
  item: RankedTheme
  registerRef: (el: HTMLElement | null) => void
}) {
  const domain = DOMAINS[item.theme.domain]
  return (
    <div className="gr__large" ref={registerRef}>
      <div className="gr__large-circle" style={{ borderColor: domain.color }}>
        <img src={illustrationSrc(item.theme.id)} alt={item.theme.nameJa} />
      </div>
      <span className="gr__large-rank" style={{ background: domain.color }}>
        {item.rank}
      </span>
      <span className="gr__large-name">{item.theme.nameJa}</span>
    </div>
  )
}

function SmallBadge({
  item,
  registerRef,
}: {
  item: RankedTheme
  registerRef: (el: HTMLElement | null) => void
}) {
  const domain = DOMAINS[item.theme.domain]
  return (
    <div className="gr__small" ref={registerRef}>
      <div className="gr__small-circle" style={{ borderColor: domain.color, color: domain.color }}>
        {item.rank}
      </div>
      <span className="gr__small-name">{item.theme.nameJa}</span>
    </div>
  )
}
