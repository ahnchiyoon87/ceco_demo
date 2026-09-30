// Organize real nodes by category without removing nodes or inventing links.
export function manufacturingPositions(nodes) {
  const order = ['Device', 'ControlPoint', 'Sensor', 'Asset', 'Document', 'DocumentSection']
  const groups = new Map()
  for (const node of nodes) {
    const kind = node.entityClass || 'Other'
    if (!groups.has(kind)) groups.set(kind, [])
    groups.get(kind).push(node)
  }
  const kinds = [...groups.keys()].sort((a,b) => {
    const rank = x => order.includes(x) ? order.indexOf(x) : order.length
    return rank(a)-rank(b) || a.localeCompare(b)
  })
  const maxRows = Math.max(1, ...[...groups.values()].map(group => group.length))
  const height = Math.max(520, (maxRows-1)*64)
  const positions = new Map()
  kinds.forEach((kind,column) => {
    const group = groups.get(kind).slice().sort((a,b)=>String(a.label||a.id).localeCompare(String(b.label||b.id)) || String(a.id).localeCompare(String(b.id)))
    group.forEach((node,row)=>positions.set(node.id, {
      x:column*255,
      y:group.length===1 ? height/2 : row*height/(group.length-1),
    }))
  })
  return positions
}
