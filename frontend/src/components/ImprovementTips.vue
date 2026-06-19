<script setup lang="ts">
defineProps<{ tips: string[] }>();
</script>

<template>
  <div v-if="tips.length" class="rounded-xl border border-amber-200 dark:border-amber-800 bg-amber-50 dark:bg-amber-900/20 p-5">
    <h3 class="text-sm font-semibold text-amber-800 dark:text-amber-300 mb-3 flex items-center gap-2">
      <span aria-hidden="true">💡</span>
      Pistes d'amélioration suggérées
    </h3>
    <ul class="space-y-2">
      <li v-for="(tip, i) in tips" :key="i" class="flex gap-2 text-sm text-amber-900 dark:text-amber-200">
        <span class="mt-0.5 shrink-0 text-amber-500 dark:text-amber-400">›</span>
        <span>{{ tip }}</span>
      </li>
    </ul>
    <p class="mt-3 text-xs text-amber-700 dark:text-amber-400">
      Ces suggestions sont générées par l'IA. Elles peuvent vous aider à modifier et améliorer votre site à l'étape suivante.
    </p>
  </div>
</template>
