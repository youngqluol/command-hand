<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { RouterLink } from 'vue-router'

import { curriculum, curriculumError, curriculumLoading, loadUnits } from '../stores/curriculum'
import { isLoggedIn } from '../stores/session'
import type { Unit } from '../types'
import InlineText from '../components/InlineText.vue'

onMounted(() => loadUnits())

/** 按区域分组。后端 `/units` 已按 ZONE_ORDER 返回，这里保持出现顺序即可。 */
const zones = computed(() => {
  const grouped = new Map<string, Unit[]>()
  for (const unit of curriculum.value) {
    const bucket = grouped.get(unit.zone)
    if (bucket) bucket.push(unit)
    else grouped.set(unit.zone, [unit])
  }
  return [...grouped.entries()].map(([zone, units], index) => ({
    zone,
    zoneIndex: index + 1,
    units,
    done: units.filter((unit) => unit.status === 'done').length,
  }))
})

function statusLabel(unit: Unit): string {
  if (!unit.status) return '未开始'
  if (unit.status === 'done') return '已通关'
  if (unit.status === 'current') return '进行中'
  return '未解锁'
}

/** 未登录时后端不下发状态，此时所有单元都可点进去看内容（但不能记录进度）。 */
function clickable(unit: Unit): boolean {
  return !isLoggedIn.value || unit.status !== 'locked'
}
</script>

<template>
  <section class="units-page">
    <header class="page-heading">
      <div>
        <p class="eyebrow">课程地图</p>
        <h1>21 天训练营</h1>
        <p class="muted">6 个主题区域，按运维现场的真实顺序推进。完成一个单元的全部题目即可解锁下一个。</p>
      </div>
      <p v-if="!isLoggedIn" class="muted hint">未登录：可自由浏览所有单元内容，进度不会被保存。</p>
    </header>

    <p v-if="curriculumLoading && !curriculum.length" class="muted">正在加载课程…</p>
    <p v-else-if="curriculumError" class="feedback error-feedback">{{ curriculumError }}</p>

    <div v-for="zone in zones" :key="zone.zone" class="zone-block panel">
      <div class="section-heading">
        <div>
          <p class="eyebrow">区域 Z{{ String(zone.zoneIndex).padStart(2, '0') }}</p>
          <h2>
            {{ zone.zone }}
            <span>{{ String(zone.done).padStart(2, '0') }} / {{ String(zone.units.length).padStart(2, '0') }}</span>
          </h2>
        </div>
      </div>

      <div class="unit-grid">
        <template v-for="unit in zone.units" :key="unit.id">
          <RouterLink
            v-if="clickable(unit)"
            class="unit-card"
            :class="unit.status ?? 'unknown'"
            :to="{ name: 'unit', params: { id: unit.id } }"
          >
            <div class="unit-card-head">
              <span class="unit-order">{{ String(unit.order).padStart(2, '0') }}</span>
              <span class="chip unit-status">{{ statusLabel(unit) }}</span>
            </div>
            <strong>{{ unit.title }}</strong>
            <small><InlineText :text="unit.goal" /></small>
            <div class="unit-card-foot">
              <span>{{ unit.completed_quests }} / {{ unit.quest_count }} 题</span>
              <span class="xp">{{ unit.xp_total }} XP</span>
            </div>
          </RouterLink>

          <div v-else class="unit-card locked" :title="`完成前一个单元后解锁`">
            <div class="unit-card-head">
              <span class="unit-order">{{ String(unit.order).padStart(2, '0') }}</span>
              <span class="chip unit-status">未解锁</span>
            </div>
            <strong>{{ unit.title }}</strong>
            <small><InlineText :text="unit.goal" /></small>
            <div class="unit-card-foot">
              <span>{{ unit.quest_count }} 题</span>
              <span class="xp">{{ unit.xp_total }} XP</span>
            </div>
          </div>
        </template>
      </div>
    </div>
  </section>
</template>
