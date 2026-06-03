<template>
  <el-card header="用户管理 (仅管理员)">
    <el-button type="primary" @click="fetchUsers" :loading="loading" style="margin-bottom: 12px">刷新</el-button>
    <el-button type="success" @click="showAdd = true" style="margin-bottom: 12px">添加用户</el-button>
    <el-table :data="users" v-loading="loading" stripe>
      <el-table-column prop="username" label="用户名" width="160" />
      <el-table-column prop="role" label="角色" width="120">
        <template #default="{ row }"><el-tag :type="row.role === 'admin' ? 'danger' : ''" size="small">{{ row.role }}</el-tag></template>
      </el-table-column>
      <el-table-column prop="created_at" label="创建时间">
        <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="120">
        <template #default="{ row }">
          <el-button v-if="row.username !== 'admin'" type="danger" size="small" @click="deleteUser(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>
    <el-dialog v-model="showAdd" title="添加用户" width="400px">
      <el-form :model="addForm" label-width="80px">
        <el-form-item label="用户名"><el-input v-model="addForm.username" /></el-form-item>
        <el-form-item label="密码"><el-input v-model="addForm.password" type="password" show-password /></el-form-item>
        <el-form-item label="角色">
          <el-select v-model="addForm.role" style="width:100%">
            <el-option label="运维人员" value="operator" />
            <el-option label="只读" value="viewer" />
            <el-option label="管理员" value="admin" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer><el-button @click="showAdd = false">取消</el-button><el-button type="primary" @click="addUser" :loading="addLoading">确定</el-button></template>
    </el-dialog>
  </el-card>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import api from '../api'
import { ElMessage, ElMessageBox } from 'element-plus'

const users = ref([]), loading = ref(false), showAdd = ref(false), addLoading = ref(false)
const addForm = reactive({ username: '', password: '', role: 'operator' })

function formatTime(ts) {
  if (!ts) return '—'
  return new Date(ts * 1000).toLocaleString()
}

async function fetchUsers() {
  loading.value = true
  try {
    const res = await api.get('/auth/users')
    users.value = Array.isArray(res) ? res : (res.users || [])
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '加载失败')
  } finally { loading.value = false }
}

async function addUser() {
  if (!addForm.username || !addForm.password) return ElMessage.warning('请填写完整')
  addLoading.value = true
  try {
    await api.post('/auth/users', addForm)
    ElMessage.success('添加成功')
    showAdd.value = false
    fetchUsers()
  } catch (e) { ElMessage.error(e.response?.data?.detail || '添加失败') } finally { addLoading.value = false }
}

async function deleteUser(row) {
  try {
    await ElMessageBox.confirm(`确定删除用户 ${row.username}?`, '确认')
    await api.delete(`/auth/users/${row.username}`)
    ElMessage.success('已删除')
    fetchUsers()
  } catch {}
}

onMounted(fetchUsers)
</script>
