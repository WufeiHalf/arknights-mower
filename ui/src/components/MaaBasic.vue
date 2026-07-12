<script setup>
import { inject, onMounted, ref, computed } from 'vue'
const axios = inject('axios')

const mobile = inject('mobile')

import { useConfigStore } from '@/stores/config'
const store = useConfigStore()

import { storeToRefs } from 'pinia'
const {
  maa_path,
  maa_conn_preset,
  maa_touch_option,
  maa_startup_check,
  maa_update_source,
  maa_update_channel,
  maa_mirrorchyan_cdk,
  maa_update_proxy
} = storeToRefs(store)

import { folder_dialog } from '@/utils/dialog'

const MUMU_MAC_STABLE = 'MuMuMacStable'

async function select_maa_dir() {
  const folder_path = await folder_dialog()
  if (folder_path) {
    maa_path.value = folder_path
  }
}

const maa_msg = ref('')
const maa_testing = ref(false)
const available_sources = ref(['github', 'mirrorchyan'])

const source_options = computed(() =>
  [
    { label: 'GitHub', value: 'github' },
    { label: 'MirrorChyan', value: 'mirrorchyan' }
  ].map((opt) => ({
    ...opt,
    disabled: !available_sources.value.includes(opt.value)
  }))
)

const channel_options = [
  { label: '正式版', value: 'stable' },
  { label: 'Beta', value: 'beta' },
  { label: '每夜', value: 'alpha' }
]

async function load_available_sources() {
  try {
    const response = await axios.get(
      `${import.meta.env.VITE_HTTP_URL}/maa-update/available-sources`
    )
    available_sources.value = response.data.sources || []
    if (
      !available_sources.value.includes(maa_update_source.value) &&
      available_sources.value.length
    ) {
      maa_update_source.value = available_sources.value[0]
    }
  } catch {
    // keep defaults
  }
}

onMounted(load_available_sources)

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

async function test_maa() {
  if (maa_testing.value) return
  maa_testing.value = true
  maa_msg.value = '正在测试……'
  try {
    let response = await axios.get(`${import.meta.env.VITE_HTTP_URL}/check-maa`)
    let data = response.data
    if (typeof data === 'string') {
      maa_msg.value = data
      return
    }
    while (data.status === 'running') {
      maa_msg.value = data.message || '正在测试……'
      await sleep(1000)
      response = await axios.get(`${import.meta.env.VITE_HTTP_URL}/check-maa/status`)
      data = response.data
      if (typeof data === 'string') {
        maa_msg.value = data
        return
      }
    }
    maa_msg.value = data.message || '测试失败，请检查Maa日志！'
  } catch (error) {
    maa_msg.value = `测试失败：${error.message}`
  } finally {
    maa_testing.value = false
  }
}

const maa_conn_presets = ref([])

async function get_maa_conn_presets() {
  const response = await axios.get(`${import.meta.env.VITE_HTTP_URL}/maa-conn-preset`)
  maa_conn_presets.value = response.data.map((x) => {
    const label = x === MUMU_MAC_STABLE ? `${x}（MuMu Mac 推荐）` : x
    return { label, value: x }
  })
}

const maa_touch_options = ['maatouch', 'minitouch', 'adb'].map((x) => {
  return { label: x, value: x }
})
</script>

<template>
  <n-card title="Maa设置">
    <template #header>Maa设置<help-text>刷理智、信用相关、领奖励、肉鸽保全等</help-text></template>
    <n-form
      :label-placement="mobile ? 'top' : 'left'"
      :show-feedback="false"
      label-width="96"
      label-align="left"
    >
      <n-form-item label="Maa目录">
        <n-input type="textarea" :autosize="true" v-model:value="maa_path" />
        <n-button @click="select_maa_dir" class="dialog-btn">...</n-button>
      </n-form-item>
      <n-form-item label="连接配置">
        <n-select :options="maa_conn_presets" v-model:value="maa_conn_preset" />
        <n-button @click="get_maa_conn_presets" class="dialog-btn">刷新</n-button>
      </n-form-item>
      <n-form-item label="触控模式">
        <n-select v-model:value="maa_touch_option" :options="maa_touch_options" />
      </n-form-item>
      <n-form-item label="启动前测试">
        <n-checkbox v-model:checked="maa_startup_check">启动Mower前测试Maa连接</n-checkbox>
      </n-form-item>
      <n-form-item label="更新源">
        <n-select v-model:value="maa_update_source" :options="source_options" />
      </n-form-item>
      <n-form-item label="更新渠道">
        <n-select v-model:value="maa_update_channel" :options="channel_options" />
      </n-form-item>
      <n-form-item v-if="maa_update_source === 'mirrorchyan'" label="MirrorChyan CDK">
        <n-input v-model:value="maa_mirrorchyan_cdk" type="password" show-password-on="click" />
      </n-form-item>
      <n-form-item label="更新代理">
        <n-input v-model:value="maa_update_proxy" placeholder="http://127.0.0.1:7890" />
      </n-form-item>
    </n-form>
    <n-divider />
    <div class="misc-container">
      <n-button :loading="maa_testing" :disabled="maa_testing" @click="test_maa">
        测试连接
      </n-button>
      <div>{{ maa_msg }}</div>
    </div>
  </n-card>
</template>

<style scoped lang="scss">
p {
  margin: 0 0 10px 0;
}

.misc-container {
  margin-top: 12px;
  display: flex;
  align-items: center;
  gap: 12px;
}
</style>
