/**
 * Circle positions traced from the coach's blank graphic-recording template
 * (public/graphic-recording-template.png), expressed as percentages of the
 * template image's width/height so they stay aligned regardless of how the
 * template is scaled on screen.
 *
 * x, y: center position (% of container width / height)
 * d: diameter (% of container width; height matches via aspect-ratio: 1)
 */
export interface LayoutSlot {
  x: number
  y: number
  d: number
}

// Ranks 1-5, left to right along the template's top ribbon.
export const TOP5_LAYOUT: LayoutSlot[] = [
  { x: 17.892, y: 18.784, d: 24.797 },
  { x: 40.209, y: 34.785, d: 22.745 },
  { x: 59.064, y: 17.362, d: 20.222 },
  { x: 77.683, y: 29.25, d: 18.555 },
  { x: 87.388, y: 52.753, d: 18.298 },
]

// Ranks 30-34, left to right along the template's bottom ribbon.
export const BOTTOM5_LAYOUT: LayoutSlot[] = [
  { x: 13.189, y: 82.275, d: 17.315 },
  { x: 31.274, y: 86.63, d: 17.999 },
  { x: 49.829, y: 85.632, d: 17.315 },
  { x: 68.298, y: 84.997, d: 18.042 },
  { x: 85.998, y: 87.719, d: 16.161 },
]

// Ranks 6-29, left to right along the ribbon's small stem nodes. Diameter
// is a fixed size (the traced radii vary with detection noise) rather than
// the traced value.
const MID24_DIAMETER = 2.2
const MID24_CENTERS: Array<[number, number]> = [
  [8.711, 69.858],
  [10.485, 68.315],
  [12.751, 67.559],
  [14.974, 67.71],
  [17.091, 67.922],
  [25.064, 69.737],
  [29.81, 70.614],
  [32.311, 71.128],
  [40.348, 71.915],
  [41.289, 70.402],
  [42.636, 72.005],
  [45.094, 72.278],
  [47.36, 72.278],
  [57.322, 72.338],
  [58.882, 70.13],
  [59.438, 72.217],
  [61.447, 72.247],
  [71.387, 71.794],
  [73.012, 71.128],
  [74.893, 70.463],
  [76.496, 69.313],
  [78.1, 68.194],
  [79.254, 66.742],
  [80.451, 64.927],
]

export const MID24_LAYOUT: LayoutSlot[] = MID24_CENTERS.map(([x, y]) => ({
  x,
  y,
  d: MID24_DIAMETER,
}))

if (TOP5_LAYOUT.length !== 5 || BOTTOM5_LAYOUT.length !== 5 || MID24_LAYOUT.length !== 24) {
  throw new Error('template layout slot counts must be 5 / 24 / 5')
}
