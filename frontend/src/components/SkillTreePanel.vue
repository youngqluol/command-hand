<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import { skillTree } from '../stores/session'
import type { SkillZone } from '../types'

const router = useRouter()
const activeZoneIndex = ref(0)

const zones = computed(() => skillTree.value?.zones ?? [])
const currentZone = computed<SkillZone | null>(() => zones.value[activeZoneIndex.value] ?? null)

// 进度刷新后区域数量可能变化（首次登录才拿到技能树），把越界的下标拉回来。
watch(zones, (next) => {
  if (activeZoneIndex.value >= next.length) activeZoneIndex.value = 0
})

/** 第一个未解锁的节点就是「当前可挑战」的位置。 */
function firstLockedIndex(zone: SkillZone): number {
  return zone.nodes.findIndex((node) => !node.unlocked)
}

/** 连线高亮的边界：到最后一个「连续已解锁」的节点为止。 */
function firstDoneIndex(zone: SkillZone): number {
  let i = 0
  for (; i < zone.nodes.length - 1; i++) {
    if (!zone.nodes[i].unlocked || !zone.nodes[i + 1].unlocked) return i
  }
  return zone.nodes.length - 1
}

function openUnit(unitId: number): void {
  router.push({ name: 'unit', params: { id: unitId } })
}
</script>

<template>
  <section class="skill-card panel">
    <div class="section-heading">
      <div>
        <p class="eyebrow">
          技能树{{
            skillTree
              ? ` · 总进度 ${skillTree.unlocked_nodes} / ${skillTree.total_nodes} (${skillTree.total_percent}%)`
              : ' · 登录后同步'
          }}
        </p>
        <h2>
          {{ currentZone?.zone ?? '文件工坊' }}
          <span>
            {{ String(currentZone?.unlocked_nodes ?? 0).padStart(2, '0') }} /
            {{ String(currentZone?.total_nodes ?? 0).padStart(2, '0') }}
          </span>
        </h2>
      </div>
      <div v-if="zones.length" class="skill-zone-switch">
        <button
          v-for="(zone, idx) in zones"
          :key="zone.zone"
          :class="['zone-chip', { active: activeZoneIndex === idx }]"
          :title="zone.zone"
          @click="activeZoneIndex = idx"
        >
          Z{{ String(zone.zone_index).padStart(2, '0') }}
        </button>
      </div>
    </div>

    <div v-if="currentZone" class="skill-path">
      <template v-for="(node, i) in currentZone.nodes" :key="node.unit_id">
        <button
          type="button"
          :class="[
            'skill',
            'skill-button',
            node.unlocked ? 'done' : i === firstLockedIndex(currentZone) ? 'current' : '',
          ]"
          :title="`进入单元 ${node.title}`"
          @click="openUnit(node.unit_id)"
        >
          <i>{{ node.unlocked ? '✓' : String(node.index).padStart(2, '0') }}</i>
          <span>{{ node.title }}</span>
        </button>
        <div
          v-if="i < currentZone.nodes.length - 1"
          :class="['link', i < firstDoneIndex(currentZone) ? 'active-link' : '']"
        ></div>
      </template>
    </div>
    <p v-else class="muted skill-empty">登录后即可看到 21 个单元的技能树进度。</p>
  </section>
</template>
