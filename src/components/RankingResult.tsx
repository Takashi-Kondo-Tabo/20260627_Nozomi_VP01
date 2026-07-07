import { DOMAINS } from '../data/themes'
import type { ParseResult } from '../lib/parseRanking'

interface Props {
  result: ParseResult
  sourceLabel: string
}

export function RankingResult({ result, sourceLabel }: Props) {
  const { ranking, isComplete, missingRanks, warnings } = result

  return (
    <section className="ranking-result">
      <h2>解析結果（{sourceLabel}）</h2>

      {!isComplete && (
        <p role="alert" className="ranking-result__incomplete">
          34資質のうち{ranking.length}件のみ認識できました。
          {missingRanks.length > 0 && `未検出の順位: ${missingRanks.join(', ')}`}
        </p>
      )}
      {warnings.map((w) => (
        <p key={w} role="alert" className="ranking-result__warning">
          {w}
        </p>
      ))}

      <ol className="ranking-result__list">
        {ranking.map(({ rank, theme }) => {
          const domain = DOMAINS[theme.domain]
          const isEdge = rank <= 5 || rank >= 30
          return (
            <li
              key={rank}
              className={isEdge ? 'ranking-result__item ranking-result__item--edge' : 'ranking-result__item'}
              style={{ borderColor: domain.color }}
            >
              <span className="ranking-result__rank" style={{ background: domain.color }}>
                {rank}
              </span>
              <span className="ranking-result__name">{theme.nameJa}</span>
              <span className="ranking-result__domain">{domain.labelJa}</span>
            </li>
          )
        })}
      </ol>
    </section>
  )
}
