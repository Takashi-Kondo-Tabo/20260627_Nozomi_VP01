import { useLayoutEffect, useRef, useState, type RefObject } from 'react'
import type { Point } from './smoothPath'

/**
 * Measures the center of each ref'd badge element relative to a container,
 * re-measuring on resize (the badges wrap responsively, so positions shift
 * with viewport width).
 */
export function useFlowPositions(
  containerRef: RefObject<HTMLElement | null>,
  itemRefs: { current: (HTMLElement | null)[] },
  deps: readonly unknown[],
): Point[] {
  const [points, setPoints] = useState<Point[]>([])
  const frame = useRef<number | null>(null)

  useLayoutEffect(() => {
    function measure() {
      const container = containerRef.current
      if (!container) return
      const containerRect = container.getBoundingClientRect()
      const next: Point[] = []
      for (const el of itemRefs.current) {
        if (!el) continue
        const rect = el.getBoundingClientRect()
        next.push({
          x: rect.left + rect.width / 2 - containerRect.left,
          y: rect.top + rect.height / 2 - containerRect.top,
        })
      }
      setPoints(next)
    }

    measure()

    function scheduleMeasure() {
      if (frame.current != null) cancelAnimationFrame(frame.current)
      frame.current = requestAnimationFrame(measure)
    }

    const resizeObserver = new ResizeObserver(scheduleMeasure)
    if (containerRef.current) resizeObserver.observe(containerRef.current)
    window.addEventListener('resize', scheduleMeasure)

    return () => {
      resizeObserver.disconnect()
      window.removeEventListener('resize', scheduleMeasure)
      if (frame.current != null) cancelAnimationFrame(frame.current)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)

  return points
}
