import { useState } from 'react'
import { RankingInput } from './components/RankingInput'
import { ParseFeedback } from './components/ParseFeedback'
import { GraphicRecording } from './components/GraphicRecording'
import type { ParseResult } from './lib/parseRanking'
import './App.css'

function App() {
  const [parsed, setParsed] = useState<{ result: ParseResult; sourceLabel: string } | null>(null)

  return (
    <main>
      <header className="app-header">
        <h1>CliftonStrengths 34 ビジュアライザー</h1>
        <p>クライアントの34資質のランキングを読み込んで、資質の全体像を可視化します。</p>
      </header>

      <RankingInput onParsed={(result, sourceLabel) => setParsed({ result, sourceLabel })} />

      {parsed && (
        <>
          <ParseFeedback result={parsed.result} sourceLabel={parsed.sourceLabel} />
          <button type="button" className="print-button" onClick={() => window.print()}>
            PDFとして保存（印刷ダイアログを開く）
          </button>
          <div className="print-area">
            <GraphicRecording ranking={parsed.result.ranking} />
          </div>
        </>
      )}
    </main>
  )
}

export default App
