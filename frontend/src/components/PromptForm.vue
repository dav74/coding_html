<script setup lang="ts">
import { ref, onUnmounted } from "vue";
import type { UploadedImage } from "../composables/useSiteGenerator";

defineProps<{ loading: boolean }>();

const emit = defineEmits<{
  generate: [prompt: string, images: UploadedImage[]];
}>();

const prompt = ref("");
const uploadedImages = ref<UploadedImage[]>([]);

function handleFiles(e: Event) {
  const files = (e.target as HTMLInputElement).files;
  if (!files) return;
  for (const file of files) {
    if (!file.type.startsWith("image/")) continue;
    uploadedImages.value.push({ file, description: "", preview: URL.createObjectURL(file) });
  }
  (e.target as HTMLInputElement).value = "";
}

function removeImage(index: number) {
  URL.revokeObjectURL(uploadedImages.value[index].preview);
  uploadedImages.value.splice(index, 1);
}

onUnmounted(() => {
  for (const img of uploadedImages.value) URL.revokeObjectURL(img.preview);
});

function submit() {
  emit("generate", prompt.value, uploadedImages.value);
}
</script>

<template>
  <form @submit.prevent="submit" class="space-y-5">
    <!-- Prompt -->
    <div>
      <label for="prompt" class="block text-sm font-semibold text-slate-700 mb-2">
        Décrivez le site que vous souhaitez créer
      </label>
      <textarea
        id="prompt"
        v-model="prompt"
        :disabled="loading"
        rows="5"
        placeholder="Exemples : un site vitrine pour un club de photo passionné par la faune sauvage · un portfolio pour un graphiste spécialisé en typographie · un site d'information sur les volcans pour un lycée…"
        class="w-full rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none transition disabled:opacity-50 disabled:cursor-not-allowed shadow-sm"
      ></textarea>
    </div>

    <!-- Upload d'images -->
    <div class="space-y-3">
      <div class="flex items-center justify-between">
        <span class="text-sm font-semibold text-slate-700">
          Images à intégrer
          <span class="font-normal text-slate-400">(optionnel)</span>
        </span>
        <label
          class="cursor-pointer inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium text-slate-700 bg-slate-100 hover:bg-slate-200 border border-slate-300 transition"
          :class="{ 'opacity-50 pointer-events-none': loading }"
        >
          <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
          </svg>
          Ajouter des images
          <input type="file" multiple accept="image/*" class="hidden" :disabled="loading" @change="handleFiles" />
        </label>
      </div>

      <div v-if="uploadedImages.length" class="grid grid-cols-2 sm:grid-cols-3 gap-3">
        <div
          v-for="(img, i) in uploadedImages"
          :key="img.preview"
          class="relative rounded-xl border border-slate-200 overflow-hidden bg-white shadow-sm"
        >
          <img :src="img.preview" :alt="img.file.name" class="w-full h-28 object-cover" />
          <button
            type="button"
            @click="removeImage(i)"
            :disabled="loading"
            class="absolute top-1.5 right-1.5 w-6 h-6 rounded-full bg-black/50 hover:bg-black/70 text-white text-xs flex items-center justify-center transition disabled:opacity-50"
            aria-label="Supprimer l'image"
          >✕</button>
          <div class="p-2 space-y-1">
            <p class="text-xs text-slate-500 truncate" :title="img.file.name">{{ img.file.name }}</p>
            <input
              v-model="img.description"
              :disabled="loading"
              type="text"
              placeholder="Description (optionnel)"
              class="w-full rounded-md border border-slate-200 bg-slate-50 px-2 py-1 text-xs text-slate-700 placeholder-slate-400 focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-transparent disabled:opacity-50 transition"
            />
          </div>
        </div>
      </div>

      <p v-if="!uploadedImages.length" class="text-xs text-slate-400">
        Vous pouvez ajouter des photos qui seront intégrées dans le site généré. Ajoutez une description pour guider l'IA dans leur utilisation.
      </p>
    </div>

    <!-- Bouton -->
    <button
      type="submit"
      :disabled="loading || !prompt.trim()"
      class="inline-flex items-center gap-2 rounded-xl bg-slate-700 px-6 py-3 text-sm font-semibold text-white shadow hover:bg-slate-600 focus:outline-none focus:ring-2 focus:ring-slate-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed transition"
    >
      <span v-if="loading" class="animate-spin w-4 h-4 border-2 border-white border-t-transparent rounded-full inline-block"></span>
      {{ loading ? "Génération en cours…" : "Générer le site" }}
    </button>
  </form>
</template>
