import * as pdfjsLib from 'pdfjs-dist'
import pdfjsWorkerUrl from 'pdfjs-dist/build/pdf.worker.mjs?url'

pdfjsLib.GlobalWorkerOptions.workerSrc = pdfjsWorkerUrl

/**
 * Extracts plain text from a PDF file, page by page, up to maxPages.
 * The client's personal CliftonStrengths ranking always appears on the
 * first page or two of a Gallup report, but maxPages leaves headroom for
 * report layouts that differ across report vintages.
 */
export async function extractTextFromPdf(file: File, maxPages = 30): Promise<string> {
  const buffer = await file.arrayBuffer()
  const pdf = await pdfjsLib.getDocument({ data: buffer }).promise

  const pageCount = Math.min(pdf.numPages, maxPages)
  const pageTexts: string[] = []

  for (let pageNumber = 1; pageNumber <= pageCount; pageNumber++) {
    const page = await pdf.getPage(pageNumber)
    const content = await page.getTextContent()
    const pageText = content.items
      .map((item) => ('str' in item ? item.str : ''))
      .join(' ')
    pageTexts.push(pageText)
  }

  return pageTexts.join('\n')
}
