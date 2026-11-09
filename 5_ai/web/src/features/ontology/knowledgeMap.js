// Fixed category columns and local relationship emphasis follow HYD's remote
// enterprise.js at 6f350503a78ca792cbcdf29a803d87da17867018.
export const groups = [
  {key:'resource',title:'설비·센서',color:'#526174',classes:['Device','Asset','Component','Sensor','ControlPoint','Department']},
  {key:'diagnosis',title:'이상·원인',color:'#b42318',classes:['Symptom','AlarmSignature','FailureMode','Cause','Check']},
  {key:'action',title:'조치·판단',color:'#0f766e',classes:['WorkMaster','Action','Decision','InputData']},
  {key:'evidence',title:'문서·근거',color:'#6d28d9',classes:['Document','DocumentSection']},
  {key:'value',title:'성과 지표',color:'#9a6700',classes:['KPI','Objective','Measure']},
  {key:'other',title:'기타 연결',color:'#6b7280',classes:[]},
]
export const kinds={Device:'공정',Asset:'설비',Component:'구성 요소',Sensor:'센서',ControlPoint:'제어 항목',Department:'담당 부서',Symptom:'증상',AlarmSignature:'경보 조건',FailureMode:'고장 유형',Cause:'원인',Check:'확인 방법',WorkMaster:'정비 절차',Action:'조치',Decision:'판단',InputData:'판단 입력',Document:'문서',DocumentSection:'문서 내용',KPI:'성과 지표',Objective:'목표',Measure:'측정 지표'}
export const relations={EXPOSES_ASSET:'설비 포함',DESCRIBED_BY:'설명 문서',INSTALLED_IN:'설치 위치',HAS_SENSOR:'연결 센서',GOVERNED_BY:'적용 정책',HAS_PROCEDURE:'대응 절차',HAS_SECTION:'문서 내용',EXPOSES_SENSOR:'제공 센서',EXPOSES_POINT:'제어 항목',OFFERS_WORK:'정비 절차 제공',FEEDS:'공급 대상',PART_OF:'소속 설비',INVESTIGATED_BY:'조사 절차',DOCUMENTED_IN:'근거 문서',TRIGGERS_DECISION:'시작하는 판단',OBSERVED_ON:'관측 설비',INDICATES:'나타내는 고장',ON_SENSOR:'관측 센서',HAS_CAUSE:'가능한 원인',CHECKED_BY:'확인 방법',MANIFESTS_AS:'나타나는 증상',AFFECTS:'영향을 주는 항목',OBSERVES:'관찰 항목',READS_COMMAND:'운전 설정 확인',PROCEDURE:'실행 절차',MITIGATES:'대응 방법',OWNED_BY:'담당 부서',INFLUENCES:'영향을 주는 지표',REQUIRES_INPUT:'필요한 입력',VERIFIED_BY:'검증 방법'}
export const kind=n=>(n.labels||[]).find(x=>!x.startsWith('_'))||'Other'
export const name=n=>String(n?.properties?.title||n?.properties?.annotation||(kind(n||{})==='WorkMaster'?n?.properties?.description:'')||n?.properties?.name||n?.label||n?.id||'이름 없음')
export const group=n=>groups.find(g=>g.classes.includes(kind(n)))||groups.at(-1)
export function context(graph,selected,query=''){
  const local=new Set(selected?[selected]:[])
  for(const e of graph.edges||[])if(e.from===selected||e.to===selected){local.add(e.from);local.add(e.to)}
  const q=query.trim().toLocaleLowerCase()
  const matches=new Set(q?(graph.nodes||[]).filter(n=>(name(n)+' '+(n.properties?.description||'')+' '+kind(n)).toLocaleLowerCase().includes(q)).map(n=>n.id):[])
  return {local,matches,dim:id=>!!(selected||q)&&!local.has(id)&&!matches.has(id)}
}
export function layout(graph,available=1200){
  const columns=groups.map(g=>({...g,nodes:(graph.nodes||[]).filter(n=>group(n).key===g.key)})).filter(g=>g.nodes.length)
  const width=Math.max(214,Math.min(320,Math.floor((available-12)/Math.max(1,columns.length))))
  const nodes=[],headings=[]
  columns.forEach((g,i)=>{
    let y=46
    const classes=[...g.classes,...new Set(g.nodes.map(kind))].filter((c,i,a)=>a.indexOf(c)===i)
    for(const cls of classes){
      const items=g.nodes.filter(n=>kind(n)===cls).sort((a,b)=>name(a).localeCompare(name(b),'ko',{numeric:true}))
      if(!items.length)continue
      headings.push({x:i*width+14,y:y+13,label:(kinds[cls]||cls)+' · '+items.length});y+=24
      for(const n of items){nodes.push({...n,x:i*width+12,y,width:width-24,color:g.color});y+=38}
      y+=12
    }
    g.height=y
  })
  const index=new Map(nodes.map(n=>[n.id,n]))
  const edges=(graph.edges||[]).map((e,i)=>{
    const a=index.get(e.from),b=index.get(e.to);if(!a||!b)return null
    const y1=a.y+16,y2=b.y+16
    let path
    if(a.x===b.x){const x=a.x+a.width;const bend=x+10+Math.min(32,Math.abs(y2-y1)/10);path=`M${x},${y1} C${bend},${y1} ${bend},${y2} ${x},${y2}`}
    else if(b.x>a.x){const x=a.x+a.width;path=`M${x},${y1} C${x+30},${y1} ${b.x-30},${y2} ${b.x},${y2}`}
    else{const x=b.x+b.width;path=`M${a.x},${y1} C${a.x-30},${y1} ${x+30},${y2} ${x},${y2}`}
    return {...e,key:i,path,description:`${name(a)} → ${relations[e.type]||e.type} → ${name(b)}`}
  }).filter(Boolean)
  return {columns,nodes,headings,edges,columnWidth:width,width:Math.max(1,columns.length)*width+12,height:Math.max(260,...columns.map(g=>g.height+12))}
}
export function shorten(text,width){
  let used=0,result=''
  for(const letter of text){used+=/[^\x00-\x7f]/.test(letter)?13:7.5;if(used>width-26)return result+'…';result+=letter}
  return result
}
