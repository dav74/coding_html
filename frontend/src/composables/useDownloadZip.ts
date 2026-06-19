import JSZip from "jszip";
import type { ResponseImage } from "./useSiteGenerator";

function base64ToUint8Array(b64: string): Uint8Array {
  const binary = atob(b64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  return bytes;
}

export async function downloadZip(
  html: string,
  css: string,
  images: ResponseImage[]
) {
  const zip = new JSZip();

  for (const img of images) {
    zip.file(`images/${img.filename}`, base64ToUint8Array(img.data));
  }

  zip.file("index.html", html);
  zip.file("style.css", css);

  const blob = await zip.generateAsync({ type: "blob" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "mon-site.zip";
  a.click();
  URL.revokeObjectURL(a.href);
}
