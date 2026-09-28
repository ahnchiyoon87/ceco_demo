// Search only the displayed schema. Entity records never enter this result.
export function searchSchemaNodes(elements, query, limit = 50) {
  const needle = query.trim().toLocaleLowerCase()
  if (!needle) return []
  const matches = data => [data.label, data.description, JSON.stringify(data.properties || {})]
    .some(value => String(value || '').toLocaleLowerCase().includes(needle))
  const related = new Set()
  for (const {data} of elements) {
    if (data.source && matches(data)) {
      related.add(data.source)
      related.add(data.target)
    }
  }
  return elements.filter(({data}) => !data.source && (matches(data) || related.has(data.id)))
    .slice(0, limit).map(({data}) => data)
}
