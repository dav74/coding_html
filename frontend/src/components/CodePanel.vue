<script setup lang="ts">
import { ref, watch, nextTick } from "vue";
import hljs from "highlight.js/lib/core";
import hljsHtml from "highlight.js/lib/languages/xml";
import hljsCss from "highlight.js/lib/languages/css";
import "highlight.js/styles/atom-one-dark.css";

hljs.registerLanguage("html", hljsHtml);
hljs.registerLanguage("css", hljsCss);

const props = defineProps<{
  title: string;
  code: string;
  language: "html" | "css";
}>();

const copied = ref(false);
const highlighted = ref("");

watch(
  () => props.code,
  async (code) => {
    if (!code) { highlighted.value = ""; return; }
    // Laisser Vue commiter le DOM (spinner caché, résultats affichés)
    // avant de lancer le calcul bloquant de hljs.
    await nextTick();
    highlighted.value = hljs.highlight(code, { language: props.language }).value;
  },
  { immediate: true }
);

function copy() {
  navigator.clipboard.writeText(props.code).then(() => {
    copied.value = true;
    setTimeout(() => (copied.value = false), 2000);
  });
}
</script>

<template>
  <div class="flex flex-col rounded-xl border border-slate-200 shadow-sm overflow-hidden">
    <div class="flex items-center justify-between px-4 py-3 border-b border-slate-700 bg-[#282c34]">
      <span class="text-sm font-semibold text-slate-200 font-mono">{{ title }}</span>
      <button
        @click="copy"
        class="inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium text-slate-300 bg-slate-700 hover:bg-slate-600 focus:outline-none focus:ring-2 focus:ring-blue-500 transition"
      >
        {{ copied ? "Copié !" : "Copier" }}
      </button>
    </div>
    <pre class="overflow-auto max-h-[70vh] m-0 rounded-none"><code class="hljs" v-html="highlighted"></code></pre>
  </div>
</template>
