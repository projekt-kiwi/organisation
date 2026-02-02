import { ref, shallowRef } from 'vue'

const DB_URL = '/kiwi.db'

async function getInitSqlJs() {
  const m = await import('sql.js')
  return m.default ?? m.Module ?? m
}

export function useKiwiDb() {
  const loading = ref(true)
  const error = ref(null)
  const db = shallowRef(null)

  const schools = ref([])
  const persons = ref([])
  const hostingOrgs = ref([])
  const workshops = ref([])
  const schoolContacts = ref([])
  const schoolWorkshops = ref([])

  async function load() {
    loading.value = true
    error.value = null
    try {
      const initSqlJs = await getInitSqlJs()
      const SQL = await initSqlJs({
        locateFile: (file) => `https://sql.js.org/dist/${file}`,
      })
      const response = await fetch(DB_URL)
      if (!response.ok) throw new Error(`Failed to load database: ${response.status}`)
      const buffer = await response.arrayBuffer()
      db.value = new SQL.Database(new Uint8Array(buffer))

      schools.value = db.value.exec('SELECT * FROM schools ORDER BY school_type, name')[0]?.values.map(([id, name, school_type]) => ({ id, name, school_type })) ?? []
      persons.value = db.value.exec('SELECT * FROM persons ORDER BY name')[0]?.values.map(([id, name, email_primary, email_secondary]) => ({ id, name, email_primary, email_secondary })) ?? []
      hostingOrgs.value = db.value.exec('SELECT * FROM hosting_organisations ORDER BY name')[0]?.values.map(([id, name]) => ({ id, name })) ?? []
      workshops.value = db.value.exec(`
        SELECT w.id, w.name, w.hosting_organisation_id, h.name as host_name
        FROM workshops w
        JOIN hosting_organisations h ON w.hosting_organisation_id = h.id
        ORDER BY h.name, w.name
      `)[0]?.values.map(([id, name, hosting_organisation_id, host_name]) => ({ id, name, hosting_organisation_id, host_name })) ?? []
      schoolContacts.value = db.value.exec('SELECT school_id, person_id FROM school_contact')[0]?.values.map(([school_id, person_id]) => ({ school_id, person_id })) ?? []
      schoolWorkshops.value = db.value.exec('SELECT school_id, workshop_id FROM school_workshop')[0]?.values.map(([school_id, workshop_id]) => ({ school_id, workshop_id })) ?? []
    } catch (e) {
      error.value = e.message || String(e)
    } finally {
      loading.value = false
    }
  }

  return {
    loading,
    error,
    load,
    schools,
    persons,
    hostingOrgs,
    workshops,
    schoolContacts,
    schoolWorkshops,
  }
}
