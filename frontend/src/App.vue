<script setup lang="ts">
import { ref, onMounted, onUnmounted } from "vue";
import { useSiteGenerator } from "./composables/useSiteGenerator";
import type { UploadedImage } from "./composables/useSiteGenerator";
import { downloadZip } from "./composables/useDownloadZip";
import PromptForm from "./components/PromptForm.vue";
import CodePanel from "./components/CodePanel.vue";

const { html, css, responseImages, loading, error, generate } = useSiteGenerator();
const zipping = ref(false);
const serverWaking = ref(false);
const loadingLong = ref(false);
const showPreview = ref(false);
const previewUrl = ref<string | null>(null);
let loadingTimer: ReturnType<typeof setTimeout> | null = null;

function buildPreviewHtml(): string {
  if (!html.value) return "";
  const withCss = html.value.replace(
    /<link[^>]+rel=["']stylesheet["'][^>]*>/i,
    `<style>${css.value}</style>`
  );
  const linkGuard = [
    "<scr" + "ipt>",
    "(function(){",
    "  document.addEventListener('click',function(e){",
    "    var a=e.target.closest('a'); if(!a) return;",
    "    e.preventDefault();",
    "    var h=(a.getAttribute('href')||'').trim();",
    "    if(h.startsWith('#')&&h.length>1){",
    "      var t=document.querySelector(h);",
    "      if(t) t.scrollIntoView({behavior:'smooth'});",
    "    }",
    "  },true);",
    "})();",
    "</" + "script>",
  ].join("\n");
  return withCss.replace(/<\/body>/i, `${linkGuard}</body>`);
}

function openPreview() {
  if (previewUrl.value) URL.revokeObjectURL(previewUrl.value);
  const blob = new Blob([buildPreviewHtml()], { type: "text/html;charset=utf-8" });
  previewUrl.value = URL.createObjectURL(blob);
  showPreview.value = true;
}

function closePreview() {
  showPreview.value = false;
  if (previewUrl.value) { URL.revokeObjectURL(previewUrl.value); previewUrl.value = null; }
}

function onKeydown(e: KeyboardEvent) {
  if (e.key === "Escape") closePreview();
}
onMounted(() => window.addEventListener("keydown", onKeydown));
onUnmounted(() => window.removeEventListener("keydown", onKeydown));

onMounted(async () => {
  const apiBase = import.meta.env.VITE_API_BASE_URL ?? "";
  serverWaking.value = true;
  try {
    await fetch(`${apiBase}/api/health`);
  } catch {
    // silencieux — l'erreur éventuelle sera gérée à la génération
  } finally {
    serverWaking.value = false;
  }
});

function handleGenerate(prompt: string, images: UploadedImage[]) {
  loadingLong.value = false;
  loadingTimer = setTimeout(() => { loadingLong.value = true; }, 20_000);
  generate(prompt, images).finally(() => {
    if (loadingTimer) clearTimeout(loadingTimer);
    loadingLong.value = false;
  });
}

async function handleDownload() {
  zipping.value = true;
  try {
    await downloadZip(html.value, css.value, responseImages.value);
  } finally {
    zipping.value = false;
  }
}
</script>

<template>
  <div class="min-h-screen bg-gradient-to-br from-slate-50 to-blue-50">
    <!-- Bandeau de réveil serveur -->
    <div
      v-if="serverWaking"
      class="bg-amber-50 border-b border-amber-200 px-4 py-2 text-center text-xs text-amber-700"
    >
      Connexion au serveur en cours…
    </div>
    <main class="max-w-7xl mx-auto px-4 sm:px-6 py-8 space-y-8">
      <!-- Formulaire -->
      <section class="bg-white rounded-2xl border border-slate-200 shadow-sm p-6">
        <PromptForm :loading="loading" @generate="handleGenerate" />
      </section>

      <!-- Message d'erreur -->
      <div
        v-if="error"
        role="alert"
        class="rounded-xl border border-red-200 bg-red-50 px-5 py-4 text-sm text-red-800 flex items-start gap-3"
      >
        <svg class="w-5 h-5 text-red-500 shrink-0 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
          <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd" />
        </svg>
        <span>{{ error }}</span>
      </div>

      <!-- Spinner de chargement -->
      <div v-if="loading" class="flex flex-col items-center justify-center py-16 gap-4">
        <div class="w-12 h-12 border-4 border-blue-200 border-t-blue-600 rounded-full animate-spin"></div>
        <p class="text-sm text-slate-500">L'agent IA génère et révise votre site…</p>
        <p class="text-xs text-slate-400">Cela peut prendre 20 à 40 secondes.</p>
        <p v-if="loadingLong" class="text-xs text-amber-600 mt-1">
          Le serveur démarre après une période d'inactivité — encore 20-30 secondes…
        </p>
      </div>

      <!-- Résultats -->
      <template v-if="html && !loading">
        <!-- Boutons d'action -->
        <div class="flex flex-wrap justify-center gap-3">
          <button
            @click="openPreview"
            class="inline-flex items-center gap-2.5 rounded-xl bg-blue-600 px-7 py-3.5 text-sm font-semibold text-white shadow-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 transition"
          >
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
            </svg>
            Visualiser le site
          </button>

          <button
            @click="handleDownload"
            :disabled="zipping"
            class="inline-flex items-center gap-2.5 rounded-xl bg-emerald-600 px-7 py-3.5 text-sm font-semibold text-white shadow-md hover:bg-emerald-700 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed transition"
          >
            <span v-if="zipping" class="animate-spin w-4 h-4 border-2 border-white border-t-transparent rounded-full inline-block"></span>
            <svg v-else class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
            </svg>
            {{ zipping ? "Préparation du ZIP…" : "Télécharger le site complet (.zip)" }}
          </button>
        </div>

        <!-- Modale d'aperçu -->
        <Teleport to="body">
          <div
            v-if="showPreview"
            style="position:fixed;inset:0;z-index:9999;display:flex;flex-direction:column;"
          >
            <!-- Barre de titre -->
            <div style="display:flex;align-items:center;justify-content:space-between;padding:0.75rem 1.25rem;background:#0f172a;color:#fff;flex-shrink:0;">
              <span style="font-size:0.875rem;font-weight:600;">Aperçu du site généré</span>
              <button
                @click="closePreview"
                style="padding:0.375rem;border-radius:0.5rem;background:transparent;border:none;color:#fff;cursor:pointer;line-height:0;"
                aria-label="Fermer l'aperçu"
              >
                <svg width="20" height="20" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            <!-- iframe -->
            <iframe
              v-if="previewUrl"
              :src="previewUrl"
              sandbox="allow-scripts"
              style="flex:1;width:100%;border:none;background:#fff;min-height:0;"
              title="Aperçu du site généré"
            ></iframe>
          </div>
        </Teleport>

        <!-- Code HTML + CSS côte à côte -->
        <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
          <CodePanel title="index.html" :code="html" language="html" />
          <CodePanel title="style.css" :code="css" language="css" />
        </div>
      </template>
    </main>
  </div>
</template>
