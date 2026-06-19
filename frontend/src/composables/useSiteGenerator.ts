import { ref } from "vue";

export interface UploadedImage {
  file: File;
  description: string;
  preview: string; // object URL for thumbnail
}

export interface ResponseImage {
  filename: string;
  data: string;       // base64
  content_type: string;
}

interface GenerateResponse {
  html: string;
  css: string;
  status: string;
  images: ResponseImage[];
}

export function useSiteGenerator() {
  const html = ref("");
  const css = ref("");
  const responseImages = ref<ResponseImage[]>([]);
  const loading = ref(false);
  const error = ref("");

  async function generate(prompt: string, images: UploadedImage[]): Promise<void> {
    if (!prompt.trim()) {
      error.value = "Le prompt ne peut pas être vide.";
      return;
    }

    loading.value = true;
    error.value = "";
    html.value = "";
    css.value = "";
    responseImages.value = [];

    const apiBase = import.meta.env.VITE_API_BASE_URL ?? "";

    const formData = new FormData();
    formData.append("prompt", prompt);

    const descriptions: Record<string, string> = {};
    for (const img of images) {
      formData.append("images", img.file, img.file.name);
      if (img.description.trim()) {
        descriptions[img.file.name] = img.description.trim();
      }
    }
    formData.append("descriptions", JSON.stringify(descriptions));

    try {
      const res = await fetch(`${apiBase}/api/generate`, {
        method: "POST",
        body: formData,
      });

      if (!res.ok) {
        let detail = `Erreur serveur (${res.status}).`;
        try {
          const data = await res.json();
          detail = data.detail ?? detail;
        } catch {}
        if (res.status === 422) {
          error.value = "Le prompt est vide. Décrivez le site que vous souhaitez créer.";
        } else if (res.status === 429) {
          error.value = "Trop de requêtes. Attendez quelques instants avant de réessayer.";
        } else {
          error.value = detail;
        }
        return;
      }

      const data: GenerateResponse = await res.json();
      html.value = data.html;
      css.value = data.css;
      responseImages.value = data.images ?? [];
    } catch {
      error.value =
        "Impossible de joindre le serveur. Vérifiez votre connexion et réessayez.";
    } finally {
      loading.value = false;
    }
  }

  return { html, css, responseImages, loading, error, generate };
}
