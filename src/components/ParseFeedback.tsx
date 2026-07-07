import type { ParseResult } from '../lib/parseRanking'

interface Props {
  result: ParseResult
  sourceLabel: string
}

export function ParseFeedback({ result, sourceLabel }: Props) {
  const { ranking, isComplete, missingRanks, warnings } = result

  if (isComplete && warnings.length === 0) {
    return <p className="ranking-result__source">解析結果（{sourceLabel}）: 34資質すべてを認識しました。</p>
  }

  return (
    <section>
      <p className="ranking-result__source">解析結果（{sourceLabel}）</p>
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
    </section>
  )
}
