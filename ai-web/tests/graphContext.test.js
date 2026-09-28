import {test} from 'node:test'
import assert from 'node:assert/strict'
import {graphContext} from '../src/features/ontology/graphContext.js'

test('asset filter retains incoming device and outgoing sensor/document context without expanding unrelated branches',()=>{
  const nodes=[['device','Device'],['mixer','Asset'],['sensor','Sensor'],['manual','Document'],['section','DocumentSection'],['unrelated','Sensor']].map(([id,label])=>({id,labels:[label]}))
  const edges=[['device','mixer'],['mixer','sensor'],['mixer','manual'],['manual','section'],['device','unrelated']].map(([from,to])=>({from,to}))
  const result=graphContext({nodes,edges},'Asset')
  assert.deepEqual(result.nodes.map(n=>n.id),['device','mixer','sensor','manual'])
  assert.equal(result.edges.length,3)
})

test('missing class stays empty and incomplete input never leaves a dangling edge',()=>{
  const graph={nodes:[{id:'mixer',labels:['Asset']}],edges:[{from:'mixer',to:'missing'}]}
  assert.deepEqual(graphContext(graph,'Asset').edges,[])
  assert.deepEqual(graphContext(graph,'Document'),{nodes:[],edges:[]})
})

test('clearing the class restores the original graph without mutating it',()=>{
  const graph={nodes:[{id:'mixer',labels:['Asset']}],edges:[]}
  graphContext(graph,'Asset')
  assert.equal(graphContext(graph,''),graph)
  assert.deepEqual(graph.nodes,[{id:'mixer',labels:['Asset']}])
})
