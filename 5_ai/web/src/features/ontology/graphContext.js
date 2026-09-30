// A class selects focal nodes; their direct relationships remain visible.
export function graphContext(graph, className) {
  if (!className) return graph
  const roots = new Set(graph.nodes.filter(node => node.labels?.includes(className)).map(node => node.id))
  const visible = new Set(roots)
  for (const edge of graph.edges) {
    if (roots.has(edge.from) || roots.has(edge.to)) {
      visible.add(edge.from)
      visible.add(edge.to)
    }
  }
  const nodes = graph.nodes.filter(node => visible.has(node.id))
  const ids = new Set(nodes.map(node => node.id))
  return {nodes, edges: graph.edges.filter(edge => ids.has(edge.from) && ids.has(edge.to))}
}
