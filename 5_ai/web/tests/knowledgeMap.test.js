import test from 'node:test'
import assert from 'node:assert/strict'
import {layout,context,kind,shorten} from '../src/features/ontology/knowledgeMap.js'
const graph={nodes:[
 {id:'asset',label:'ST-103',labels:['_Entity','Asset']},
 {id:'sensor',label:'PDT-103',labels:['Sensor']},
 {id:'manual',label:'냉각수 매뉴얼',labels:['Document']},
 {id:'other',label:'교반기 원인',labels:['Cause']},
 {id:'custom',label:'새 항목',labels:['_Entity','CustomClass']},
],edges:[{from:'asset',to:'sensor',type:'HAS_SENSOR'},{from:'asset',to:'manual',type:'HAS_PROCEDURE'},{from:'other',to:'manual',type:'DOCUMENTED_IN'}]}
test('category layout retains every real node and relationship, including new classes',()=>{
 const d=layout(graph,1200)
 assert.equal(kind(graph.nodes[0]),'Asset')
 assert.deepEqual(new Set(d.nodes.map(n=>n.id)),new Set(graph.nodes.map(n=>n.id)))
 assert.equal(d.edges.length,graph.edges.length)
 assert.equal(d.columns.at(-1).key,'other')
 assert.equal(d.edges[0].description,'ST-103 → 연결 센서 → PDT-103')
 for(const n of d.nodes)assert.ok(n.x+n.width<=d.width&&n.y+32<=d.height)
})
test('selection emphasizes only direct relationships without deleting other knowledge',()=>{
 const c=context(graph,'asset')
 assert.deepEqual(c.local,new Set(['asset','sensor','manual']))
 assert.equal(c.dim('other'),true)
 assert.equal(c.dim('manual'),false)
 assert.equal(layout(graph).nodes.length,5)
 const reset=context(graph,'')
 assert.ok(graph.nodes.every(n=>!reset.dim(n.id)))
})
test('search matches remain visible while another item is selected',()=>{
 const c=context(graph,'asset','교반기')
 assert.ok(c.matches.has('other'))
 assert.equal(c.dim('other'),false)
 assert.equal(c.dim('custom'),true)
})
test('narrow screens scroll the map instead of shrinking Korean labels',()=>{
 const d=layout(graph,300)
 assert.ok(d.width>300)
 assert.ok(d.nodes.every(n=>n.width>=190))
 assert.ok(shorten('가나다라마바사아자차카타파하가나다라마바사아자차카타파하',190).endsWith('…'))
})
