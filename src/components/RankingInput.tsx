import { useState, type ChangeEvent } from 'react'
import { extractTextFromPdf } from '../lib/extractPdfText'
import { parseRankingFromText, type ParseResult } from '../lib/parseRanking'

interface Props {
  onParsed: (result: ParseResult, sourceLabel: string) => void
}

export function RankingInput({ onParsed }: Props) {
  const [pasteText, setPasteText] = useState('')
  const [isReadingPdf, setIsReadingPdf] = useState(false)
  const [pdfError, setPdfError] = useState<string | null>(null)

  async function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (!file) return

    setPdfError(null)
    setIsReadingPdf(true)
    try {
      const text = await extractTextFromPdf(file)
      const result = parseRankingFromText(text)
      onParsed(result, `PDF: ${file.name}`)
    } catch (err) {
      setPdfError(
        `PDFの読み取りに失敗しました: ${err instanceof Error ? err.message : String(err)}`,
      )
    } finally {
      setIsReadingPdf(false)
    }
  }

  function handlePasteSubmit() {
    if (!pasteText.trim()) return
    const result = parseRankingFromText(pasteText)
    onParsed(result, 'テキスト貼り付け')
  }

  return (
    <section className="ranking-input">
      <div className="ranking-input__block">
        <h2>1. GallupのPDFレポートから読み込む</h2>
        <p>CliftonStrengths 34の結果PDFをアップロードしてください。ブラウザ内で処理され、サーバーには送信されません。</p>
        <input type="file" accept="application/pdf" onChange={handleFileChange} disabled={isReadingPdf} />
        {isReadingPdf && <p>解析中…</p>}
        {pdfError && <p role="alert" className="ranking-input__error">{pdfError}</p>}
      </div>

      <div className="ranking-input__block">
        <h2>2. またはテキストを貼り付け</h2>
        <p>「1. 戦略性」のように、順位と資質名の並んだテキストを貼り付けてください。</p>
        <textarea
          value={pasteText}
          onChange={(e) => setPasteText(e.target.value)}
          rows={8}
          placeholder={'1. 戦略性\n2. 最上志向\n3. 親密性\n…'}
        />
        <button type="button" onClick={handlePasteSubmit} disabled={!pasteText.trim()}>
          解析する
        </button>
      </div>
    </section>
  )
}
