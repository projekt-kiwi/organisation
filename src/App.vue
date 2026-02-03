<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useKiwiDb } from './composables/useKiwiDb'

const {
  loading,
  error,
  load,
  schools,
  persons,
  hostingOrgs,
  workshops,
  schoolContacts,
  schoolWorkshops,
} = useKiwiDb()

const activeTab = ref('organisation') // 'organisation' | 'schools' | 'workshops' | 'dates'

const bgBrgFreistadtPdfUrl = `${import.meta.env.BASE_URL}documents/bgbrgfreistadt.pdf`
function isBgBrgFreistadt(schoolName) {
  return schoolName && (schoolName === 'BG/BRG Freistadt' || String(schoolName).includes('Freistadt'))
}

const dateSuggestions = ref([])
const dateSuggestionsLoading = ref(false)
const dateSuggestionsError = ref(null)

function parseCsvRow(line) {
  const out = []
  let i = 0
  while (i < line.length) {
    if (line[i] === '"') {
      i += 1
      let field = ''
      while (i < line.length && line[i] !== '"') {
        field += line[i]
        i += 1
      }
      if (line[i] === '"') i += 1
      out.push(field.trim())
      if (line[i] === ',') i += 1
    } else {
      let field = ''
      while (i < line.length && line[i] !== ',') {
        field += line[i]
        i += 1
      }
      out.push(field.trim())
      if (line[i] === ',') i += 1
    }
  }
  return out
}

function formatDateRange(dateFrom, dateTo) {
  if (!dateFrom && !dateTo) return null
  const from = dateFrom || dateTo
  const to = dateTo || dateFrom
  if (from === to) return formatDate(from)
  return `${formatDate(from)} – ${formatDate(to)}`
}

function formatDate(iso) {
  if (!iso || !/^\d{4}-\d{2}-\d{2}$/.test(iso)) return iso
  const [y, m, d] = iso.split('-')
  return `${d}.${m}.${y}`
}

function formatTimeRange(timeFrom, timeTo) {
  if (!timeFrom && !timeTo) return null
  if (timeFrom && timeTo) return `${timeFrom} – ${timeTo}`
  return timeFrom || timeTo
}

async function loadDateSuggestions() {
  dateSuggestionsLoading.value = true
  dateSuggestionsError.value = null
  try {
    const res = await fetch(`${import.meta.env.BASE_URL}date_suggestions.csv`)
    if (!res.ok) throw new Error(`Failed to load: ${res.status}`)
    const text = await res.text()
    const lines = text.split(/\r?\n/).filter((l) => l.trim())
    if (lines.length < 2) {
      dateSuggestions.value = []
      return
    }
    const headers = parseCsvRow(lines[0])
    const rows = []
    for (let i = 1; i < lines.length; i++) {
      const vals = parseCsvRow(lines[i])
      const row = {}
      headers.forEach((h, j) => {
        row[h] = (vals[j] ?? '').trim()
      })
      rows.push(row)
    }
    const bySchool = new Map()
    for (const r of rows) {
      const name = r.School || 'Unbekannt'
      if (!bySchool.has(name)) {
        bySchool.set(name, {
          school: name,
          schoolType: r.School_Type || '',
          correspondent: r.Correspondent || '',
          email: r.Email || '',
          slots: [],
        })
      }
      bySchool.get(name).slots.push({
        description: r.Timeslot_Description || '',
        dateFrom: r.Date_From || '',
        dateTo: r.Date_To || '',
        timeFrom: r.Time_From || '',
        timeTo: r.Time_To || '',
        unitsNotes: r.Units_Notes || '',
      })
    }
    dateSuggestions.value = [...bySchool.values()].sort((a, b) =>
      a.school.localeCompare(b.school)
    )
  } catch (e) {
    dateSuggestionsError.value = e.message || String(e)
  } finally {
    dateSuggestionsLoading.value = false
  }
}
const expandedDateSchoolKey = ref(null) // Terminvorschläge tab: expand by school name
const expandedSchoolGroupName = ref(null) // Schule tab: expand by school name (groups Sek I + Sek II)
const expandedWorkshopId = ref(null)
const expandedWorkshopInListId = ref(null) // for "by workshop" tab
const expandedSchoolInOrgKey = ref(null) // Organisation tab: "workshopId-schoolName" when school group expanded

// Group schools by name so Sek I and Sek II appear as one entry
const groupedSchools = computed(() => {
  const byName = new Map()
  for (const s of schools.value) {
    if (!byName.has(s.name)) {
      byName.set(s.name, { name: s.name, ids: [], schoolTypes: [] })
    }
    const g = byName.get(s.name)
    g.ids.push(s.id)
    g.schoolTypes.push(s.school_type)
  }
  return [...byName.values()].sort((a, b) => a.name.localeCompare(b.name))
})

// Dates tab: merge CSV respondents with schools from DB that have no slots (show email + contact message)
const dateSlotsCards = computed(() => {
  const responded = new Set(dateSuggestions.value.map((c) => c.school))
  const noResponseCards = groupedSchools.value
    .filter((g) => !responded.has(g.name))
    .map((g) => {
      const contacts = contactsForSchoolGroup(g.ids)
      const firstEmail = contacts[0]?.email_primary || contacts[0]?.email_secondary || ''
      return {
        school: g.name,
        schoolType: g.schoolTypes.join('; '),
        correspondent: '',
        email: firstEmail,
        slots: [],
        noResponse: true,
      }
    })
  return [...dateSuggestions.value, ...noResponseCards].sort((a, b) =>
    a.school.localeCompare(b.school)
  )
})

function contactsForSchool(schoolId) {
  const personIds = schoolContacts.value
    .filter((sc) => sc.school_id === schoolId)
    .map((sc) => sc.person_id)
  return persons.value.filter((p) => personIds.includes(p.id))
}

function contactsForSchoolGroup(schoolIds) {
  const seen = new Set()
  const out = []
  for (const id of schoolIds) {
    for (const c of contactsForSchool(id)) {
      if (!seen.has(c.id)) {
        seen.add(c.id)
        out.push(c)
      }
    }
  }
  return out.sort((a, b) => a.name.localeCompare(b.name))
}

function workshopsForSchool(schoolId) {
  const workshopIds = schoolWorkshops.value
    .filter((sw) => sw.school_id === schoolId)
    .map((sw) => sw.workshop_id)
  return workshops.value.filter((w) => workshopIds.includes(w.id))
}

function workshopsForSchoolGroup(schoolIds) {
  const seen = new Set()
  const out = []
  for (const id of schoolIds) {
    for (const w of workshopsForSchool(id)) {
      if (!seen.has(w.id)) {
        seen.add(w.id)
        out.push(w)
      }
    }
  }
  return out.sort((a, b) => (a.host_name || '').localeCompare(b.host_name || '') || a.name.localeCompare(b.name))
}

function schoolsForWorkshop(workshopId) {
  const schoolIds = schoolWorkshops.value
    .filter((sw) => sw.workshop_id === workshopId)
    .map((sw) => sw.school_id)
  return schools.value.filter((s) => schoolIds.includes(s.id))
}

// Same schools as schoolsForWorkshop but grouped by school name (Sek I + Sek II together)
function schoolsForWorkshopGrouped(workshopId) {
  const flat = schoolsForWorkshop(workshopId)
  const byName = new Map()
  for (const s of flat) {
    if (!byName.has(s.name)) {
      byName.set(s.name, { name: s.name, ids: [], schoolTypes: [] })
    }
    const g = byName.get(s.name)
    g.ids.push(s.id)
    g.schoolTypes.push(s.school_type)
  }
  return [...byName.values()].sort((a, b) => a.name.localeCompare(b.name))
}

function workshopsForOrg(orgId) {
  return workshops.value.filter((w) => w.hosting_organisation_id === orgId)
}

function toggleSchoolGroupExpand(groupName) {
  expandedSchoolGroupName.value = expandedSchoolGroupName.value === groupName ? null : groupName
}

function toggleDateSchool(schoolName) {
  expandedDateSchoolKey.value = expandedDateSchoolKey.value === schoolName ? null : schoolName
}

function toggleWorkshopExpand(id) {
  expandedWorkshopId.value = expandedWorkshopId.value === id ? null : id
}

function toggleWorkshopInListExpand(id) {
  expandedWorkshopInListId.value = expandedWorkshopInListId.value === id ? null : id
}

function schoolInOrgExpandKey(workshopId, schoolName) {
  return `${workshopId}-${schoolName}`
}
function toggleSchoolInOrgExpand(workshopId, schoolName) {
  const key = schoolInOrgExpandKey(workshopId, schoolName)
  expandedSchoolInOrgKey.value = expandedSchoolInOrgKey.value === key ? null : key
}

onMounted(load)
watch(activeTab, (tab) => {
  if (tab === 'dates') loadDateSuggestions()
})
</script>

<template>
  <div class="app">
    <header class="header">
      <h1>KIWi Consortium – Datenbank</h1>
      <p class="subtitle">Schulen, Ansprechpersonen & Workshops</p>
    </header>

    <div v-if="loading" class="loading">
      <div class="spinner" aria-hidden="true"></div>
      <p>Datenbank wird geladen …</p>
    </div>

    <div v-else-if="error" class="error">
      <p><strong>Fehler:</strong> {{ error }}</p>
      <button type="button" class="btn" @click="load">Erneut laden</button>
    </div>

    <template v-else>
      <nav class="tabs" role="tablist" aria-label="Ansicht">
        <button
          type="button"
          role="tab"
          class="tab"
          :class="{ active: activeTab === 'organisation' }"
          :aria-selected="activeTab === 'organisation'"
          @click="activeTab = 'organisation'"
        >
          Organisation
        </button>
        <button
          type="button"
          role="tab"
          class="tab"
          :class="{ active: activeTab === 'schools' }"
          :aria-selected="activeTab === 'schools'"
          @click="activeTab = 'schools'"
        >
          Schule
        </button>
        <button
          type="button"
          role="tab"
          class="tab"
          :class="{ active: activeTab === 'workshops' }"
          :aria-selected="activeTab === 'workshops'"
          @click="activeTab = 'workshops'"
        >
          Workshop
        </button>
        <button
          type="button"
          role="tab"
          class="tab"
          :class="{ active: activeTab === 'dates' }"
          :aria-selected="activeTab === 'dates'"
          @click="activeTab = 'dates'"
        >
          Terminvorschläge
        </button>
      </nav>

      <section v-show="activeTab === 'organisation'" class="results partners-view">
        <div v-for="org in hostingOrgs" :key="org.id" class="partner-block">
          <h2 class="partner-name">{{ org.name }}</h2>
          <ul class="workshop-cards">
            <li
              v-for="workshop in workshopsForOrg(org.id)"
              :key="workshop.id"
              class="workshop-card"
              :class="{ expanded: expandedWorkshopId === workshop.id }"
            >
            <button
              type="button"
              class="workshop-card-header"
              :aria-expanded="expandedWorkshopId === workshop.id"
              @click="toggleWorkshopExpand(workshop.id)"
            >
              <span class="workshop-card-title">{{ workshop.name }}</span>
              <span class="workshop-card-count">
                {{ schoolsForWorkshopGrouped(workshop.id).length }} {{ schoolsForWorkshopGrouped(workshop.id).length === 1 ? 'Schule' : 'Schulen' }}
              </span>
                <span class="expand-icon" aria-hidden="true">{{ expandedWorkshopId === workshop.id ? '−' : '+' }}</span>
              </button>
              <div v-show="expandedWorkshopId === workshop.id" class="workshop-card-details">
                <ul class="school-list-inline school-list-expandable">
                  <li
                    v-for="group in schoolsForWorkshopGrouped(workshop.id)"
                    :key="group.name"
                    class="school-inline-card-wrapper"
                    :class="{ expanded: expandedSchoolInOrgKey === schoolInOrgExpandKey(workshop.id, group.name) }"
                  >
                    <button
                      type="button"
                      class="school-inline-card school-inline-card-btn"
                      :aria-expanded="expandedSchoolInOrgKey === schoolInOrgExpandKey(workshop.id, group.name)"
                      @click="toggleSchoolInOrgExpand(workshop.id, group.name)"
                    >
                      <span class="school-name">{{ group.name }}</span>
                      <span class="school-type">{{ group.schoolTypes.join(', ') }}</span>
                      <span class="expand-icon" aria-hidden="true">{{ expandedSchoolInOrgKey === schoolInOrgExpandKey(workshop.id, group.name) ? '−' : '+' }}</span>
                    </button>
                    <div v-show="expandedSchoolInOrgKey === schoolInOrgExpandKey(workshop.id, group.name)" class="school-contacts-inline">
                      <h4 class="contacts-inline-title">Ansprechpersonen</h4>
                      <ul v-if="contactsForSchoolGroup(group.ids).length" class="contact-list">
                        <li v-for="c in contactsForSchoolGroup(group.ids)" :key="c.id" class="contact">
                          <span class="contact-name">{{ c.name }}</span>
                          <a v-if="c.email_primary" :href="`mailto:${c.email_primary}`" class="contact-email">{{ c.email_primary }}</a>
                          <a v-else-if="c.email_secondary" :href="`mailto:${c.email_secondary}`" class="contact-email">{{ c.email_secondary }}</a>
                        </li>
                      </ul>
                      <p v-else class="muted">Keine Ansprechpersonen hinterlegt.</p>
                    </div>
                  </li>
                </ul>
                <p v-if="!schoolsForWorkshopGrouped(workshop.id).length" class="muted">Keine Schulen zugeordnet.</p>
              </div>
            </li>
          </ul>
        </div>
      </section>

      <section v-show="activeTab === 'schools'" class="results">
        <p class="results-count">
          {{ groupedSchools.length }} {{ groupedSchools.length === 1 ? 'Schule' : 'Schulen' }}
        </p>
        <ul class="school-list">
          <li
            v-for="group in groupedSchools"
            :key="group.name"
            class="school-card"
            :class="{ expanded: expandedSchoolGroupName === group.name }"
          >
            <button
              type="button"
              class="school-header"
              :aria-expanded="expandedSchoolGroupName === group.name"
              @click="toggleSchoolGroupExpand(group.name)"
            >
              <span class="school-name">{{ group.name }}</span>
              <span class="school-type">{{ group.schoolTypes.join(', ') }}</span>
              <span class="expand-icon" aria-hidden="true">{{ expandedSchoolGroupName === group.name ? '−' : '+' }}</span>
            </button>
            <div v-show="expandedSchoolGroupName === group.name" class="school-details">
              <div v-if="contactsForSchoolGroup(group.ids).length" class="block">
                <h3>Ansprechpersonen</h3>
                <ul class="contact-list">
                  <li v-for="c in contactsForSchoolGroup(group.ids)" :key="c.id" class="contact">
                    <span class="contact-name">{{ c.name }}</span>
                    <a v-if="c.email_primary" :href="`mailto:${c.email_primary}`" class="contact-email">{{ c.email_primary }}</a>
                    <a v-else-if="c.email_secondary" :href="`mailto:${c.email_secondary}`" class="contact-email">{{ c.email_secondary }}</a>
                  </li>
                </ul>
              </div>
              <div v-if="workshopsForSchoolGroup(group.ids).length" class="block">
                <h3>Workshops</h3>
                <ul class="workshop-list">
                  <li v-for="w in workshopsForSchoolGroup(group.ids)" :key="w.id" class="workshop">
                    <span class="workshop-name">{{ w.name }}</span>
                    <span class="workshop-host">{{ w.host_name }}</span>
                  </li>
                </ul>
              </div>
              <p v-if="!contactsForSchoolGroup(group.ids).length && !workshopsForSchoolGroup(group.ids).length" class="muted">
                Keine Kontakte oder Workshops hinterlegt.
              </p>
            </div>
          </li>
        </ul>
      </section>

      <section v-show="activeTab === 'workshops'" class="results workshops-view">
        <p class="results-count">
          {{ workshops.length }} {{ workshops.length === 1 ? 'Workshop' : 'Workshops' }}
        </p>
        <ul class="workshop-cards workshop-list-flat">
          <li
            v-for="workshop in workshops"
            :key="workshop.id"
            class="workshop-card"
            :class="{ expanded: expandedWorkshopInListId === workshop.id }"
          >
            <button
              type="button"
              class="workshop-card-header"
              :aria-expanded="expandedWorkshopInListId === workshop.id"
              @click="toggleWorkshopInListExpand(workshop.id)"
            >
              <span class="workshop-card-title">{{ workshop.name }}</span>
              <span class="workshop-card-host">{{ workshop.host_name }}</span>
              <span class="workshop-card-count">
                {{ schoolsForWorkshopGrouped(workshop.id).length }} {{ schoolsForWorkshopGrouped(workshop.id).length === 1 ? 'Schule' : 'Schulen' }}
              </span>
              <span class="expand-icon" aria-hidden="true">{{ expandedWorkshopInListId === workshop.id ? '−' : '+' }}</span>
            </button>
            <div v-show="expandedWorkshopInListId === workshop.id" class="workshop-card-details">
              <ul class="school-list-inline">
                <li
                  v-for="group in schoolsForWorkshopGrouped(workshop.id)"
                  :key="group.name"
                  class="school-inline-card"
                >
                  <span class="school-name">{{ group.name }}</span>
                  <span class="school-type">{{ group.schoolTypes.join(', ') }}</span>
                </li>
              </ul>
              <p v-if="!schoolsForWorkshopGrouped(workshop.id).length" class="muted">Keine Schulen zugeordnet.</p>
            </div>
          </li>
        </ul>
      </section>

      <section v-show="activeTab === 'dates'" class="results dates-view">
        <div v-if="dateSuggestionsLoading" class="loading">
          <div class="spinner" aria-hidden="true"></div>
          <p>Terminvorschläge werden geladen …</p>
        </div>
        <div v-else-if="dateSuggestionsError" class="error">
          <p><strong>Fehler:</strong> {{ dateSuggestionsError }}</p>
          <button type="button" class="btn" @click="loadDateSuggestions">Erneut laden</button>
        </div>
        <template v-else>
          <p class="results-count">
            {{ dateSlotsCards.length }} {{ dateSlotsCards.length === 1 ? 'Schule' : 'Schulen' }}
          </p>
          <ul class="date-slots-list">
            <li
              v-for="(card, index) in dateSlotsCards"
              :key="index"
              class="date-slots-card"
              :class="{ expanded: expandedDateSchoolKey === card.school, 'no-response': card.noResponse }"
            >
              <button
                type="button"
                class="date-slots-card-header"
                :aria-expanded="expandedDateSchoolKey === card.school"
                @click="toggleDateSchool(card.school)"
              >
                <span class="date-slots-school-name">{{ card.school }}</span>
                <span v-if="card.schoolType" class="date-slots-type-inline">{{ card.schoolType }}</span>
                <span class="date-slots-count">
                  <template v-if="card.noResponse">—</template>
                  <template v-else>{{ card.slots.length }} {{ card.slots.length === 1 ? 'Termin' : 'Termine' }}</template>
                </span>
                <span class="expand-icon" aria-hidden="true">{{ expandedDateSchoolKey === card.school ? '−' : '+' }}</span>
              </button>
              <div v-show="expandedDateSchoolKey === card.school" class="date-slots-card-details">
                <div v-if="isBgBrgFreistadt(card.school)" class="date-slots-document">
                  <a :href="bgBrgFreistadtPdfUrl" target="_blank" rel="noopener noreferrer" class="date-slots-document-link">Dokument ansehen (PDF) ↗</a>
                </div>
                <template v-if="card.noResponse">
                  <div v-if="card.email" class="date-slots-contact">
                    <a :href="`mailto:${card.email}`" class="date-slots-email">{{ card.email }}</a>
                  </div>
                  <p class="date-slots-contact-message">Contact directly for appointments scheduling.</p>
                </template>
                <template v-else>
                  <div v-if="card.correspondent || card.email" class="date-slots-contact">
                    <span v-if="card.correspondent" class="date-slots-correspondent">Correspondent: {{ card.correspondent }}</span>
                    <a v-if="card.email" :href="`mailto:${card.email}`" class="date-slots-email">Email: {{ card.email }}</a>
                  </div>
                  <ul class="date-slots-slots">
                    <li
                      v-for="(slot, slotIndex) in card.slots"
                      :key="slotIndex"
                      class="date-slots-slot"
                    >
                      <span class="date-slots-slot-desc">{{ slot.description }}</span>
                      <span v-if="formatDateRange(slot.dateFrom, slot.dateTo)" class="date-slots-slot-date">
                        {{ formatDateRange(slot.dateFrom, slot.dateTo) }}
                      </span>
                      <span v-if="formatTimeRange(slot.timeFrom, slot.timeTo)" class="date-slots-slot-time">
                        {{ formatTimeRange(slot.timeFrom, slot.timeTo) }}
                      </span>
                      <span v-if="slot.unitsNotes" class="date-slots-slot-notes">{{ slot.unitsNotes }}</span>
                    </li>
                  </ul>
                  <p v-if="!card.slots.length" class="muted">Keine Terminangaben.</p>
                </template>
              </div>
            </li>
          </ul>
        </template>
      </section>
    </template>
  </div>
</template>

<style>
*,
*::before,
*::after {
  box-sizing: border-box;
}

body {
  margin: 0;
  font-family: 'DM Sans', system-ui, sans-serif;
  font-size: 16px;
  line-height: 1.5;
  color: #1a1a1a;
  background: #f5f2ed;
}

.app {
  max-width: 56rem;
  margin: 0 auto;
  padding: 2rem 1.5rem;
}

.header {
  margin-bottom: 2rem;
}

.header h1 {
  margin: 0 0 0.25rem;
  font-size: 1.75rem;
  font-weight: 600;
  letter-spacing: -0.02em;
}

.subtitle {
  margin: 0;
  color: #5c5c5c;
  font-size: 0.95rem;
}

.loading,
.error {
  text-align: center;
  padding: 3rem 1rem;
}

.spinner {
  width: 2.5rem;
  height: 2.5rem;
  margin: 0 auto 1rem;
  border: 3px solid #e0ddd8;
  border-top-color: #2d6a4f;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.error {
  background: #fef2f2;
  border-radius: 0.5rem;
  color: #991b1b;
}

.btn {
  margin-top: 0.75rem;
  padding: 0.5rem 1rem;
  font: inherit;
  font-size: 0.9rem;
  color: #fff;
  background: #2d6a4f;
  border: none;
  border-radius: 0.375rem;
  cursor: pointer;
}

.btn:hover {
  background: #1b4332;
}

.tabs {
  display: flex;
  gap: 0.25rem;
  margin-bottom: 1.5rem;
  border-bottom: 1px solid #e0ddd8;
}

.tab {
  padding: 0.6rem 1rem;
  font: inherit;
  font-size: 0.9rem;
  font-weight: 500;
  color: #5c5c5c;
  background: none;
  border: none;
  border-bottom: 2px solid transparent;
  margin-bottom: -1px;
  cursor: pointer;
  transition: color 0.15s, border-color 0.15s;
}

.tab:hover {
  color: #1a1a1a;
}

.tab.active {
  color: #2d6a4f;
  border-bottom-color: #2d6a4f;
}

.results-count {
  margin: 0 0 1rem;
  font-size: 0.9rem;
  color: #5c5c5c;
}

.school-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.school-card {
  background: #fff;
  border-radius: 0.5rem;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06);
  overflow: hidden;
}

.school-header {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 1rem 1.25rem;
  font: inherit;
  text-align: left;
  color: inherit;
  background: none;
  border: none;
  cursor: pointer;
  transition: background 0.15s;
}

.school-header:hover {
  background: #faf9f7;
}

.school-name {
  flex: 1;
  font-weight: 600;
  font-size: 1rem;
}

.school-type {
  font-size: 0.85rem;
  color: #5c5c5c;
  font-family: 'JetBrains Mono', monospace;
}

.expand-icon {
  width: 1.5rem;
  height: 1.5rem;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 1.1rem;
  font-weight: 600;
  color: #2d6a4f;
}

.school-details {
  padding: 0 1.25rem 1.25rem;
  border-top: 1px solid #ebe8e4;
}

.school-details .block {
  margin-top: 1rem;
}

.school-details .block:first-child {
  margin-top: 1rem;
}

.school-details h3 {
  margin: 0 0 0.5rem;
  font-size: 0.8rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: #5c5c5c;
}

.contact-list,
.workshop-list {
  list-style: none;
  margin: 0;
  padding: 0;
}

.contact,
.workshop {
  padding: 0.35rem 0;
  font-size: 0.9rem;
}

.contact-name,
.workshop-name {
  display: block;
  font-weight: 500;
}

.contact-email {
  display: block;
  font-size: 0.85rem;
  color: #2d6a4f;
  text-decoration: none;
  font-family: 'JetBrains Mono', monospace;
}

.contact-email:hover {
  text-decoration: underline;
}

.workshop-host {
  font-size: 0.85rem;
  color: #5c5c5c;
}

.muted {
  margin: 1rem 0 0;
  font-size: 0.9rem;
  color: #5c5c5c;
}

/* Partners tab */
.partners-view {
  margin-top: 0;
}

.partner-block {
  margin-bottom: 2.5rem;
}

.partner-block:last-child {
  margin-bottom: 0;
}

.partner-name {
  margin: 0 0 1rem;
  font-size: 1.15rem;
  font-weight: 600;
  color: #1a1a1a;
  letter-spacing: -0.01em;
}

.workshop-cards {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.workshop-card {
  background: #fff;
  border-radius: 0.5rem;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06);
  overflow: hidden;
}

.workshop-card-header {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 1rem 1.25rem;
  font: inherit;
  text-align: left;
  color: inherit;
  background: none;
  border: none;
  cursor: pointer;
  transition: background 0.15s;
}

.workshop-card-header:hover {
  background: #faf9f7;
}

.workshop-card-title {
  flex: 1;
  font-weight: 600;
  font-size: 1rem;
}

.workshop-card-count {
  font-size: 0.85rem;
  color: #5c5c5c;
}

.workshop-card-host {
  font-size: 0.85rem;
  color: #5c5c5c;
  font-family: 'JetBrains Mono', monospace;
}

.workshops-view .workshop-list-flat {
  margin-top: 0;
}

.workshop-card-details {
  padding: 0 1.25rem 1.25rem;
  border-top: 1px solid #ebe8e4;
}

.school-list-inline {
  list-style: none;
  margin: 1rem 0 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.school-inline-card {
  padding: 0.6rem 0.75rem;
  background: #faf9f7;
  border-radius: 0.375rem;
  font-size: 0.9rem;
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.school-inline-card .school-name {
  font-weight: 500;
}

.school-inline-card .school-type {
  font-size: 0.8rem;
  font-family: 'JetBrains Mono', monospace;
  color: #5c5c5c;
}

/* Expandable school under Organisation → Workshop */
.school-list-expandable {
  gap: 0.5rem;
}

.school-inline-card-wrapper {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.school-inline-card-btn {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.6rem 0.75rem;
  font: inherit;
  text-align: left;
  color: inherit;
  background: #faf9f7;
  border: none;
  border-radius: 0.375rem;
  cursor: pointer;
  transition: background 0.15s;
}

.school-inline-card-btn:hover {
  background: #f0ede8;
}

.school-inline-card-btn .school-name {
  flex: 1;
  font-weight: 500;
}

.school-inline-card-btn .expand-icon {
  width: 1.25rem;
  height: 1.25rem;
  font-size: 1rem;
}

.school-contacts-inline {
  margin-top: 0.5rem;
  margin-left: 0.75rem;
  padding: 0.75rem 1rem;
  background: #fff;
  border-radius: 0.375rem;
  border: 1px solid #ebe8e4;
}

.contacts-inline-title {
  margin: 0 0 0.5rem;
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: #5c5c5c;
}

.school-contacts-inline .contact-list {
  list-style: none;
  margin: 0;
  padding: 0;
}

.school-contacts-inline .contact {
  padding: 0.35rem 0;
  font-size: 0.9rem;
}

.school-contacts-inline .contact-email {
  display: block;
  font-size: 0.85rem;
  color: #2d6a4f;
  text-decoration: none;
  font-family: 'JetBrains Mono', monospace;
}

.school-contacts-inline .contact-email:hover {
  text-decoration: underline;
}

/* Terminvorschläge tab – one card per school */
.dates-view {
  margin-top: 0;
}

.dates-view .loading,
.dates-view .error {
  text-align: center;
  padding: 2rem 1rem;
}

.date-slots-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.date-slots-card {
  background: #fff;
  border-radius: 0.5rem;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06);
  overflow: hidden;
}

.date-slots-card-header {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 1rem 1.25rem;
  font: inherit;
  text-align: left;
  color: inherit;
  background: none;
  border: none;
  cursor: pointer;
  transition: background 0.15s;
}

.date-slots-card-header:hover {
  background: #faf9f7;
}

.date-slots-card-header .date-slots-school-name {
  flex: 1;
  margin: 0;
  font-size: 1rem;
  font-weight: 600;
  color: #1a1a1a;
  letter-spacing: -0.01em;
}

.date-slots-type-inline {
  font-size: 0.85rem;
  color: #5c5c5c;
  font-family: 'JetBrains Mono', monospace;
}

.date-slots-count {
  font-size: 0.85rem;
  color: #5c5c5c;
}

.date-slots-card-details {
  padding: 0 1.25rem 1.25rem;
  border-top: 1px solid #ebe8e4;
}

.date-slots-document {
  margin-bottom: 0.75rem;
}

.date-slots-document-link {
  display: inline-block;
  font-size: 0.9rem;
  font-weight: 500;
  color: #2d6a4f;
  text-decoration: none;
}

.date-slots-document-link:hover {
  text-decoration: underline;
}

.date-slots-card-details .date-slots-contact {
  margin-top: 0.75rem;
  margin-bottom: 0.75rem;
}

.date-slots-meta {
  margin-bottom: 0.35rem;
}

.date-slots-type {
  font-size: 0.8rem;
  color: #5c5c5c;
  font-family: 'JetBrains Mono', monospace;
}

.date-slots-contact {
  margin-bottom: 0.75rem;
  font-size: 0.9rem;
}

.date-slots-correspondent {
  display: block;
  font-weight: 500;
}

.date-slots-email {
  display: block;
  font-size: 0.85rem;
  color: #2d6a4f;
  text-decoration: none;
  font-family: 'JetBrains Mono', monospace;
}

.date-slots-email:hover {
  text-decoration: underline;
}

.date-slots-contact-message {
  margin: 0.5rem 0 0;
  font-size: 0.9rem;
  color: #5c5c5c;
  font-style: italic;
}

.date-slots-slots {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.date-slots-slot {
  padding: 0.5rem 0.6rem;
  background: #faf9f7;
  border-radius: 0.375rem;
  font-size: 0.9rem;
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
}

.date-slots-slot-desc {
  font-weight: 500;
  color: #1a1a1a;
}

.date-slots-slot-date,
.date-slots-slot-time {
  font-size: 0.85rem;
  color: #5c5c5c;
  font-family: 'JetBrains Mono', monospace;
}

.date-slots-slot-notes {
  font-size: 0.85rem;
  color: #5c5c5c;
  line-height: 1.4;
}

.date-slots-card .muted {
  margin: 0;
  font-size: 0.9rem;
  color: #5c5c5c;
}
</style>
