export interface Point {
  x: number
  y: number
}

/**
 * Builds a smooth SVG path (Catmull-Rom -> cubic Bezier) through the given
 * points, returning one "M x y C ... C ..." segment string per consecutive
 * pair so each segment can be stroked with a different color.
 */
export function buildSmoothSegments(points: Point[]): string[] {
  if (points.length < 2) return []

  const segments: string[] = []
  for (let i = 0; i < points.length - 1; i++) {
    const p0 = points[Math.max(0, i - 1)]
    const p1 = points[i]
    const p2 = points[i + 1]
    const p3 = points[Math.min(points.length - 1, i + 2)]

    const cp1x = p1.x + (p2.x - p0.x) / 6
    const cp1y = p1.y + (p2.y - p0.y) / 6
    const cp2x = p2.x - (p3.x - p1.x) / 6
    const cp2y = p2.y - (p3.y - p1.y) / 6

    segments.push(`M ${p1.x} ${p1.y} C ${cp1x} ${cp1y}, ${cp2x} ${cp2y}, ${p2.x} ${p2.y}`)
  }
  return segments
}
