import api from './index'

export function fetchRepairCatalog() {
  return api.get('/repair/catalog')
}

export function fetchRepairHistory() {
  return api.get('/repair/history')
}

export function triggerRepair(repairId, userConfirmed = false) {
  return api.post('/repair/trigger', { repair_id: repairId, user_confirmed: userConfirmed })
}