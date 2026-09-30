<template>
  <CollapsiblePanel title="온톨로지 스키마" :open="open" @toggle="$emit('toggle')">
    <div v-if="!schema.classes.length && !schema.relationships.length && !schemas.length" class="empty-hint">
      스키마가 아직 없습니다. 대화로 설계를 시작하세요.
    </div>

    <!-- Schema Groups -->
    <div v-for="s in schemas" :key="s.id" class="schema-group">
      <div
        class="schema-group-header"
        :class="{ active: selectedSchema === s.name }"
        @click="$emit('select-schema', s.name === selectedSchema ? null : s.name)"
      >
        <span class="schema-group-toggle">{{ expandedGroups[s.id] ? '▼' : '▶' }}</span>
        <span class="schema-group-name" @click.stop="toggleGroup(s.id)">{{ s.name }}</span>
        <span class="schema-group-count">{{ s.total_entity_count || 0 }}</span>
        <div class="schema-group-actions">
          <button
            class="btn-icon-xs"
            title="엔티티 삭제"
            @click.stop="$emit('delete-schema-entities', s.id)"
          >🗑</button>
          <button
            class="btn-icon-xs"
            title="스키마 복원 (Neo4j)"
            @click.stop="$emit('rebuild-schema', s.id)"
          >↻</button>
        </div>
      </div>
      <div v-if="expandedGroups[s.id]" class="schema-group-body">
        <!-- Classes -->
        <div v-for="cls in s.classes" :key="cls.class_name" class="schema-class indented">
          <!-- View mode -->
          <template v-if="editingClass !== cls.class_name">
            <div class="schema-class-header">
              <span class="schema-icon">C</span>
              <span class="schema-class-name">{{ cls.class_name }}</span>
              <span v-if="cls.entity_count" class="entity-count-badge">{{ cls.entity_count }}</span>
              <div class="schema-class-actions">
                <button class="btn-icon-xs" title="편집" @click.stop="startEditClass(cls, s.name)">✎</button>
                <button class="btn-icon-xs" title="삭제" @click.stop="confirmDeleteClass(cls.class_name)">✕</button>
              </div>
            </div>
            <div v-if="cls.description" class="schema-class-desc">{{ cls.description }}</div>
            <div v-for="prop in cls.properties || []" :key="prop.name" class="schema-prop">
              <span class="prop-name">{{ prop.name }}</span>
              <span class="prop-type">{{ prop.type }}</span>
              <span v-if="prop.required" class="prop-required">*</span>
            </div>
          </template>

          <!-- Edit mode -->
          <template v-else>
            <div class="edit-class-form">
              <input v-model="editForm.name" class="inline-edit-input" placeholder="클래스 이름" />
              <input v-model="editForm.description" class="inline-edit-input" placeholder="설명 (선택)" />
              <div class="edit-props-section">
                <div v-for="(prop, pi) in editForm.properties" :key="pi" class="prop-edit-row">
                  <input v-model="prop.name" class="inline-edit-input prop-name-input" placeholder="속성명" />
                  <select v-model="prop.type" class="inline-edit-select">
                    <option v-for="t in PROP_TYPES" :key="t" :value="t">{{ t }}</option>
                  </select>
                  <button class="btn-icon-xs" title="삭제" @click="editForm.properties.splice(pi, 1)">✕</button>
                </div>
                <button class="add-item-btn" @click="editForm.properties.push({ name: '', type: 'string' })">+ 속성</button>
              </div>
              <div class="edit-actions">
                <button class="btn-save-xs" @click="submitEditClass(s.name)">저장</button>
                <button class="btn-cancel-xs" @click="cancelEdit">취소</button>
              </div>
            </div>
          </template>
        </div>

        <!-- Add new class -->
        <template v-if="editingClass === `__new__${s.id}`">
          <div class="schema-class indented">
            <div class="edit-class-form">
              <input v-model="editForm.name" class="inline-edit-input" placeholder="새 클래스 이름" />
              <input v-model="editForm.description" class="inline-edit-input" placeholder="설명 (선택)" />
              <div class="edit-props-section">
                <div v-for="(prop, pi) in editForm.properties" :key="pi" class="prop-edit-row">
                  <input v-model="prop.name" class="inline-edit-input prop-name-input" placeholder="속성명" />
                  <select v-model="prop.type" class="inline-edit-select">
                    <option v-for="t in PROP_TYPES" :key="t" :value="t">{{ t }}</option>
                  </select>
                  <button class="btn-icon-xs" title="삭제" @click="editForm.properties.splice(pi, 1)">✕</button>
                </div>
                <button class="add-item-btn" @click="editForm.properties.push({ name: '', type: 'string' })">+ 속성</button>
              </div>
              <div class="edit-actions">
                <button class="btn-save-xs" @click="submitEditClass(s.name)">저장</button>
                <button class="btn-cancel-xs" @click="cancelEdit">취소</button>
              </div>
            </div>
          </div>
        </template>
        <button
          v-if="editingClass !== `__new__${s.id}`"
          class="add-item-btn indented"
          @click="startNewClass(s.id)"
        >+ 클래스 추가</button>

        <!-- Relationships -->
        <div v-if="s.relationships && s.relationships.length" class="schema-rels-section indented">
          <div v-for="rel in s.relationships" :key="`${rel.name}-${rel.from_class}-${rel.to_class}`" class="schema-rel">
            <span class="rel-from">{{ rel.from_class }}</span>
            <span class="rel-arrow">-[{{ rel.name }}]-></span>
            <span class="rel-to">{{ rel.to_class }}</span>
            <div class="schema-rel-actions">
              <button class="btn-icon-xs" title="삭제" @click.stop="confirmDeleteRel(rel)">✕</button>
            </div>
          </div>
        </div>

        <!-- Add new relationship -->
        <template v-if="addingRelFor === s.id">
          <div class="edit-rel-form indented">
            <select v-model="relForm.from_class" class="inline-edit-select">
              <option value="" disabled>From</option>
              <option v-for="c in s.classes" :key="c.class_name" :value="c.class_name">{{ c.class_name }}</option>
            </select>
            <input v-model="relForm.name" class="inline-edit-input rel-name-input" placeholder="관계명" />
            <select v-model="relForm.to_class" class="inline-edit-select">
              <option value="" disabled>To</option>
              <option v-for="c in s.classes" :key="c.class_name" :value="c.class_name">{{ c.class_name }}</option>
            </select>
            <div class="edit-actions">
              <button class="btn-save-xs" :disabled="!relForm.name || !relForm.from_class || !relForm.to_class" @click="submitNewRel(s.name)">저장</button>
              <button class="btn-cancel-xs" @click="addingRelFor = null">취소</button>
            </div>
          </div>
        </template>
        <button
          v-if="addingRelFor !== s.id"
          class="add-item-btn indented"
          @click="startNewRel(s.id)"
        >+ 관계 추가</button>
      </div>
    </div>

    <!-- Ungrouped classes -->
    <div v-if="ungroupedClasses.length" class="schema-group">
      <div class="schema-group-header ungrouped" @click="showUngrouped = !showUngrouped">
        <span class="schema-group-toggle">{{ showUngrouped ? '▼' : '▶' }}</span>
        <span class="schema-group-name">(미분류)</span>
        <span class="schema-group-count">{{ ungroupedClasses.length }}</span>
      </div>
      <div v-if="showUngrouped" class="schema-group-body">
        <div v-for="cls in ungroupedClasses" :key="cls.name" class="schema-class indented">
          <div class="schema-class-header">
            <span class="schema-icon">C</span>
            <span class="schema-class-name">{{ cls.name }}</span>
            <div class="schema-class-actions">
              <button class="btn-icon-xs" title="삭제" @click.stop="confirmDeleteClass(cls.name)">✕</button>
            </div>
          </div>
          <div v-if="cls.description" class="schema-class-desc">{{ cls.description }}</div>
          <div v-for="prop in cls.properties || []" :key="prop.name" class="schema-prop">
            <span class="prop-name">{{ prop.name }}</span>
            <span class="prop-type">{{ prop.type }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Entity counts (when no schema groups exist) -->
    <div v-if="!schemas.length && entityCounts.length" class="schema-rels-section">
      <div class="ctx-label">엔티티 수</div>
      <div v-for="entityCount in entityCounts" :key="entityCount.name" class="entity-count-item">
        <span>{{ entityCount.name }}</span>
        <span class="entity-count-badge">{{ entityCount.count }}</span>
      </div>
    </div>
  </CollapsiblePanel>
</template>

<script setup>
import { reactive, ref, computed } from 'vue'
import CollapsiblePanel from '../../shared/ui/CollapsiblePanel.vue'

const PROP_TYPES = ['string', 'integer', 'float', 'boolean', 'date', 'list']

const props = defineProps({
  entityCounts: { type: Array, required: true },
  open: { type: Boolean, required: true },
  schema: { type: Object, required: true },
  schemas: { type: Array, default: () => [] },
  selectedSchema: { type: String, default: null },
})

const emit = defineEmits([
  'toggle', 'select-schema', 'delete-schema-entities', 'rebuild-schema',
  'save-class', 'delete-class', 'save-relationship', 'delete-relationship',
])

const expandedGroups = reactive({})
const showUngrouped = ref(false)

// Edit state
const editingClass = ref(null)
const editForm = reactive({ name: '', description: '', properties: [] })
const addingRelFor = ref(null)
const relForm = reactive({ name: '', from_class: '', to_class: '', description: '' })

function toggleGroup(schemaId) {
  expandedGroups[schemaId] = !expandedGroups[schemaId]
}

const ungroupedClasses = computed(() => {
  const groupedNames = new Set()
  for (const s of props.schemas) {
    for (const c of s.classes || []) {
      groupedNames.add(c.class_name)
    }
  }
  return (props.schema.classes || []).filter(c => !groupedNames.has(c.name))
})

// Class editing
function startEditClass(cls, schemaName) {
  editingClass.value = cls.class_name
  editForm.name = cls.class_name
  editForm.description = cls.description || ''
  editForm.properties = (cls.properties || []).map(p => ({ ...p }))
  editForm._schemaName = schemaName
}

function startNewClass(schemaId) {
  editingClass.value = `__new__${schemaId}`
  editForm.name = ''
  editForm.description = ''
  editForm.properties = []
}

function cancelEdit() {
  editingClass.value = null
}

function submitEditClass(schemaName) {
  if (!editForm.name.trim()) return
  const validProps = editForm.properties.filter(p => p.name.trim())
  const isNew = editingClass.value?.startsWith('__new__')
  emit('save-class', {
    name: editForm.name.trim(),
    original_name: isNew ? '' : editingClass.value,
    description: editForm.description,
    properties: validProps,
    schema_name: schemaName,
  })
  editingClass.value = null
}

function confirmDeleteClass(className) {
  // Find entity count from schemas
  let count = 0
  for (const s of props.schemas) {
    const cls = (s.classes || []).find(c => c.class_name === className)
    if (cls?.entity_count) { count = cls.entity_count; break }
  }
  const msg = count > 0
    ? `클래스 "${className}"을(를) 삭제하시겠습니까?\n\n⚠ 이 클래스의 엔티티 ${count}개와 관련 관계 타입도 함께 삭제됩니다.`
    : `클래스 "${className}"을(를) 삭제하시겠습니까?\n(관련 관계 타입도 함께 삭제됩니다)`
  if (confirm(msg)) {
    emit('delete-class', className)
  }
}

// Relationship editing
function startNewRel(schemaId) {
  addingRelFor.value = schemaId
  relForm.name = ''
  relForm.from_class = ''
  relForm.to_class = ''
  relForm.description = ''
}

function submitNewRel(schemaName) {
  if (!relForm.name.trim() || !relForm.from_class || !relForm.to_class) return
  emit('save-relationship', {
    name: relForm.name.trim(),
    from_class: relForm.from_class,
    to_class: relForm.to_class,
    description: relForm.description,
    properties: [],
    schema_name: schemaName,
  })
  addingRelFor.value = null
}

function confirmDeleteRel(rel) {
  if (confirm(`관계 "${rel.from_class} -[${rel.name}]-> ${rel.to_class}"을(를) 삭제하시겠습니까?`)) {
    emit('delete-relationship', { name: rel.name, from_class: rel.from_class, to_class: rel.to_class })
  }
}
</script>

<style scoped>
.schema-group {
  margin-bottom: 4px;
}
.schema-group-header {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 8px;
  cursor: pointer;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 600;
  color: var(--text);
}
.schema-group-header:hover {
  background: rgba(255, 255, 255, 0.05);
}
.schema-group-header.active {
  background: rgba(0, 120, 255, 0.15);
  border-left: 2px solid var(--neo4j);
}
.schema-group-header.ungrouped {
  color: var(--text-muted);
  font-style: italic;
}
.schema-group-toggle {
  font-size: 10px;
  width: 12px;
  flex-shrink: 0;
}
.schema-group-name {
  flex: 1;
}
.schema-group-count {
  background: rgba(255, 255, 255, 0.1);
  border-radius: 8px;
  padding: 1px 6px;
  font-size: 10px;
  color: var(--text-muted);
}
.schema-group-actions {
  display: flex;
  gap: 2px;
  opacity: 0;
  transition: opacity 0.15s;
}
.schema-group-header:hover .schema-group-actions {
  opacity: 1;
}
.btn-icon-xs {
  background: none;
  border: none;
  cursor: pointer;
  font-size: 11px;
  padding: 2px 4px;
  border-radius: 3px;
  color: var(--text-muted);
}
.btn-icon-xs:hover {
  background: rgba(255, 255, 255, 0.1);
  color: var(--text);
}
.schema-group-body {
  padding-left: 8px;
}
.indented {
  padding-left: 12px;
}

/* Class actions (hover-revealed) */
.schema-class-actions,
.schema-rel-actions {
  display: flex;
  gap: 2px;
  opacity: 0;
  transition: opacity 0.15s;
  margin-left: auto;
}
.schema-class-header:hover .schema-class-actions,
.schema-rel:hover .schema-rel-actions {
  opacity: 1;
}

/* Inline editing */
.inline-edit-input {
  background: rgba(255, 255, 255, 0.08);
  border: 1px solid rgba(255, 255, 255, 0.15);
  color: var(--text);
  font-size: 12px;
  border-radius: 3px;
  padding: 3px 6px;
  width: 100%;
  box-sizing: border-box;
}
.inline-edit-input:focus {
  border-color: rgba(0, 120, 255, 0.5);
  outline: none;
}
.inline-edit-select {
  background: rgba(255, 255, 255, 0.08);
  border: 1px solid rgba(255, 255, 255, 0.15);
  color: var(--text);
  font-size: 11px;
  border-radius: 3px;
  padding: 3px 4px;
}

.edit-class-form {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 6px 0;
}
.edit-props-section {
  display: flex;
  flex-direction: column;
  gap: 3px;
  padding-left: 4px;
}
.prop-edit-row {
  display: flex;
  gap: 4px;
  align-items: center;
}
.prop-name-input {
  flex: 1;
  min-width: 0;
}
.edit-actions {
  display: flex;
  gap: 4px;
  margin-top: 2px;
}
.btn-save-xs {
  background: rgba(0, 120, 255, 0.2);
  border: 1px solid rgba(0, 120, 255, 0.4);
  color: var(--accent);
  font-size: 11px;
  padding: 3px 10px;
  border-radius: 3px;
  cursor: pointer;
}
.btn-save-xs:hover:not(:disabled) {
  background: rgba(0, 120, 255, 0.3);
}
.btn-save-xs:disabled {
  opacity: 0.4;
  cursor: default;
}
.btn-cancel-xs {
  background: none;
  border: 1px solid rgba(255, 255, 255, 0.15);
  color: var(--text-muted);
  font-size: 11px;
  padding: 3px 10px;
  border-radius: 3px;
  cursor: pointer;
}
.btn-cancel-xs:hover {
  background: rgba(255, 255, 255, 0.05);
  color: var(--text);
}
.add-item-btn {
  background: none;
  border: none;
  color: var(--text-muted);
  font-size: 11px;
  cursor: pointer;
  padding: 3px 4px;
  text-align: left;
}
.add-item-btn:hover {
  color: var(--accent);
}

/* Relationship editing */
.edit-rel-form {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  align-items: center;
  padding: 4px 0;
}
.rel-name-input {
  width: 80px;
  flex-shrink: 0;
}
.schema-rel {
  position: relative;
}
</style>
