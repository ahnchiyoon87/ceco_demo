import test from 'node:test'
import assert from 'node:assert/strict'
import {searchSchemaNodes} from '../src/features/ontology/schemaSearch.js'

const elements = [
  {data:{id:'class:Asset',label:'Asset',properties:{description:'설비'}}},
  {data:{id:'class:Sensor',label:'Sensor',properties:{description:'센서'}}},
  {data:{id:'class:Document',label:'Document',properties:{description:'문서'}}},
  {data:{id:'rel:HAS_SENSOR',source:'class:Asset',target:'class:Sensor',label:'HAS_SENSOR'}},
]
test('schema search finds class descriptions and the endpoints of matching relationships',()=>{
  assert.deepEqual(searchSchemaNodes(elements,' 센서 ').map(n=>n.id),['class:Sensor'])
  assert.deepEqual(searchSchemaNodes(elements,'has_sensor').map(n=>n.id),['class:Asset','class:Sensor'])
})
test('entity names, empty text and unmatched text produce no fabricated schema results',()=>{
  for(const query of ['LT-101','','   ','missing']) assert.deepEqual(searchSchemaNodes(elements,query),[])
  assert.equal(searchSchemaNodes(elements,'has_sensor',1).length,1)
  assert.equal(elements.length,4)
})
