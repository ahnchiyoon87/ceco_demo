<script setup>
import {ref,watch,nextTick} from 'vue'
const props=defineProps({open:Boolean})
const emit=defineEmits(['close'])
const dialog=ref(null)
watch(()=>props.open,async value=>{await nextTick();if(value)dialog.value?.showModal();else dialog.value?.close()})
</script>
<template><dialog ref="dialog" class="operator-console" aria-labelledby="operator-title" @cancel="emit('close')"><header><div><h2 id="operator-title">SCADA 운전원 제어</h2><p>가상 설비를 직접 조작합니다. AI 검토·승인 경로와 별개이며, 아래 운전값으로 반영 여부를 확인하세요.</p></div><button autofocus @click="emit('close')">닫고 관제로 돌아가기</button></header><iframe v-if="open" src="http://127.0.0.1:27018/" title="FUXA 가상 설비 운전원 화면"></iframe></dialog></template>
<style scoped>.operator-console{width:calc(100vw - 40px);max-width:1800px;height:calc(100vh - 40px);max-height:none;border:1px solid #355969;border-radius:16px;padding:0;background:#102b39;color:#e2eef4}.operator-console::backdrop{background:#061624cc}.operator-console header{display:flex;align-items:center;justify-content:space-between;padding:16px 22px;gap:20px}.operator-console h2{font-size:20px;margin:0}.operator-console p{font-size:var(--ui-font-caption);color:#b9cedb;margin:7px 0 0}.operator-console button{background:#e4f5ef;color:#165b4e;border:0;border-radius:8px;padding:12px;white-space:nowrap}.operator-console iframe{width:100%;height:calc(100% - 100px);border:0;background:#0e1b29}@media(max-width:650px){.operator-console{width:100vw;height:100dvh;border-radius:0}.operator-console header{flex-wrap:wrap}.operator-console iframe{height:calc(100% - 165px)}}</style>
