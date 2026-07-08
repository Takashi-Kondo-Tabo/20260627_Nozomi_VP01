import { useEffect, useState } from 'react'

const cache = new Map<string, string>()

interface Props {
  src: string
  className?: string
}

/**
 * Fetches an SVG file and inlines its markup directly into the DOM (rather
 * than referencing it via <img src>), so the paths stay real vector content
 * when the page is exported to PDF via the browser's print pipeline.
 */
export function InlineSvg({ src, className }: Props) {
  const [svg, setSvg] = useState<string | null>(cache.get(src) ?? null)

  useEffect(() => {
    const cached = cache.get(src)
    if (cached) {
      setSvg(cached)
      return
    }
    let cancelled = false
    fetch(src)
      .then((res) => res.text())
      .then((text) => {
        cache.set(src, text)
        if (!cancelled) setSvg(text)
      })
    return () => {
      cancelled = true
    }
  }, [src])

  if (!svg) return null
  // eslint-disable-next-line react/no-danger -- trusted, same-origin static assets we generated
  return <div className={className} dangerouslySetInnerHTML={{ __html: svg }} />
}
