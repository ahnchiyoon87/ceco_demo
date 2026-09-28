// HTML is the editable source of truth. Publish an identical offline copy.
import {copyFileSync,mkdirSync} from 'node:fs'
mkdirSync('public',{recursive:true})
copyFileSync('../docs/소스코드로_확인한_아주쉬운_시스템설명.html','public/system-guide.html')
