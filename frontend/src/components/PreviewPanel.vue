<script setup lang="ts">
import { computed } from "vue";

const props = defineProps<{
  html: string;
  css: string;
}>();

const srcdoc = computed(() => {
  if (!props.html) return "";
  return props.html.replace(
    /<link[^>]+rel=["']stylesheet["'][^>]*>/i,
    `<style>${props.css}</style>`
  );
});
</script>

<template>
  <div class="rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden">
    <div class="px-4 py-3 border-b border-slate-100 bg-slate-50">
      <span class="text-sm font-semibold text-slate-700">Aperçu en direct</span>
      <span class="ml-2 text-xs text-slate-400">(rendu dans un cadre isolé)</span>
    </div>
    <iframe
      :srcdoc="srcdoc"
      sandbox="allow-same-origin"
      class="w-full h-96 border-0"
      title="Aperçu du site généré"
    ></iframe>
  </div>
</template>
