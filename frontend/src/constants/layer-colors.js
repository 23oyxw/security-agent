/** Layer accent colors SSOT */
export const LAYER_ACCENTS = {
  L1: '#3b82f6',
  L2: '#10b981',
  GATE: '#fb923c',
  L3: '#ca8a04',
  L4: '#8b5cf6',
  L5: '#0ea5e9',
}

export function layerAccent(id) {
  return LAYER_ACCENTS[id] || '#64748b'
}