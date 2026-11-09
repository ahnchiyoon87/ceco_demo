"""Presentation-only pointer and paced real browser interactions for the film."""
import math

actions=[]
positions={}
CURSOR_SCRIPT="""(() => {
 if(window!==window.top)return;
 function install(){
  if(document.getElementById('film-pointer'))return;
  const cursor=document.createElement('div');cursor.id='film-pointer';cursor.setAttribute('aria-hidden','true');
  cursor.style.cssText='position:fixed;left:0;top:0;width:22px;height:30px;z-index:2147483647;pointer-events:none;display:none;filter:drop-shadow(0 1px 2px #0007)';
  cursor.innerHTML='<svg viewBox="0 0 22 30"><path d="M2 2V23L7 18L12 28L16 26L11 17H20Z" fill="white" stroke="#163b44" stroke-width="1.5"/></svg>';
  document.body.append(cursor);
  window.__filmPointer=(x,y)=>{cursor.style.display='block';cursor.style.transform=`translate(${x}px,${y}px)`};
  document.addEventListener('mousemove',e=>window.__filmPointer(e.clientX,e.clientY));
  document.addEventListener('mousedown',e=>{
   const ring=document.createElement('div');ring.setAttribute('aria-hidden','true');
   ring.style.cssText=`position:fixed;left:${e.clientX-16}px;top:${e.clientY-16}px;width:32px;height:32px;border:2px solid #43bba6;border-radius:50%;z-index:2147483646;pointer-events:none`;
   document.body.append(ring);ring.animate([{opacity:.9,transform:'scale(.6)'},{opacity:0,transform:'scale(1.6)'}],{duration:600});setTimeout(()=>ring.remove(),600);
  });
 }
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',install,{once:true});else install();
})()"""

async def install(context):
    await context.add_init_script(CURSOR_SCRIPT)


async def move(page,x,y):
    start=positions.get(id(page),(320,180));distance=math.hypot(x-start[0],y-start[1])
    duration=min(700,max(300,distance*.55));steps=max(10,int(duration/35))
    for i in range(1,steps+1):
        t=i/steps;eased=t*t*(3-2*t)
        px=start[0]+(x-start[0])*eased;py=start[1]+(y-start[1])*eased-12*math.sin(math.pi*t)
        await page.mouse.move(px,py)
        await page.evaluate('(p)=>window.__filmPointer?.(p.x,p.y)',{'x':px,'y':py})
        await page.wait_for_timeout(duration/steps)
    positions[id(page)]=(x,y)
    return round(duration)


async def focus(page,locator):
    await locator.wait_for(state='visible',timeout=30000)
    duration=await locator.evaluate("""async e=>{
      let parent=e.parentElement;
      while(parent&&!(parent.scrollHeight>parent.clientHeight+2&&/auto|scroll/.test(getComputedStyle(parent).overflowY)))parent=parent.parentElement;
      const scroller=parent||document.scrollingElement;
      const viewport=parent?parent.getBoundingClientRect().top:0;
      const target=Math.max(0,Math.min(scroller.scrollHeight-scroller.clientHeight,scroller.scrollTop+e.getBoundingClientRect().top-viewport-110));
      const start=scroller.scrollTop,delta=target-start;
      if(Math.abs(delta)<12)return 0;
      const duration=Math.min(1800,Math.max(850,Math.abs(delta)*.9));
      const behavior=scroller.style.scrollBehavior;scroller.style.scrollBehavior='auto';
      await new Promise(resolve=>{let begin;function frame(now){begin??=now;const t=Math.min(1,(now-begin)/duration);scroller.scrollTop=start+delta*t*t*(3-2*t);if(t<1)requestAnimationFrame(frame);else resolve()}requestAnimationFrame(frame)});
      scroller.style.scrollBehavior=behavior;return Math.round(duration);
    }""")
    if duration:actions.append({'action':'scroll','duration_ms':duration})
    await page.wait_for_timeout(350)


async def point(page,locator):
    await locator.wait_for(state='visible',timeout=30000)
    box=await locator.bounding_box();height=page.viewport_size['height']
    if not box or box['y']<10 or box['y']+box['height']>height-10:
        await focus(page,locator);box=await locator.bounding_box()
    if not box:raise RuntimeError('Filmed target is not visible')
    duration=await move(page,box['x']+box['width']/2,box['y']+min(box['height']/2,30))
    await page.wait_for_timeout(250)
    return duration


async def click(page,locator):
    duration=await point(page,locator)
    await locator.click(delay=100)
    actions.append({'action':'click','move_ms':duration})
    await page.wait_for_timeout(300)


async def check(page,locator):
    await point(page,locator);await locator.check();await page.wait_for_timeout(350)


async def fill(page,locator,text):
    await click(page,locator)
    if len(text)<=100:
        await locator.fill('');await locator.press_sequentially(text,delay=35)
    else:await locator.fill(text)
    await page.wait_for_timeout(450)


async def select(page,locator,**option):
    await point(page,locator);await locator.select_option(**option);await page.wait_for_timeout(450)
